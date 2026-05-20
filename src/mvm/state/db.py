"""SQLite connection helper with WAL + single-writer flock enforcement."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from ..config import PROJECT_ROOT

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "state.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA temp_store=MEMORY")


def init_schema(conn: sqlite3.Connection) -> None:
    """Idempotent — runs the full DDL. CREATE TABLE IF NOT EXISTS throughout."""
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()


class _FileLock:
    """Cross-platform single-writer lock on a sidecar file.

    On Windows uses msvcrt; on POSIX uses fcntl. The lock is held for the
    lifetime of the connection.
    """

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.lock_path, "w")  # noqa: SIM115 — held intentionally

    def acquire(self) -> None:
        try:
            import fcntl  # type: ignore[import-not-found]
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            import msvcrt  # type: ignore[import-not-found]
            try:
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as e:
                raise RuntimeError(f"Database is locked by another writer: {self.lock_path}") from e

    def release(self) -> None:
        try:
            import fcntl  # type: ignore[import-not-found]
            fcntl.flock(self._fh, fcntl.LOCK_UN)
        except ImportError:
            try:
                import msvcrt  # type: ignore[import-not-found]
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:  # noqa: BLE001
                pass
        try:
            self._fh.close()
        except Exception:  # noqa: BLE001
            pass


@contextmanager
def get_conn(
    path: Optional[Path] = None,
    *,
    init: bool = False,
    enforce_single_writer: bool = True,
) -> Iterator[sqlite3.Connection]:
    """Yield a connection with WAL + (optional) single-writer flock.

    When enforce_single_writer=True, acquires an OS-level file lock on
    `<db_path>.lock` for the lifetime of the connection. A second concurrent
    writer raises immediately rather than blocking forever.
    """
    db_path = Path(path) if path else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    lock = None
    if enforce_single_writer:
        lock = _FileLock(db_path.with_suffix(db_path.suffix + ".lock"))
        lock.acquire()

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    if init:
        init_schema(conn)
    try:
        yield conn
    finally:
        try:
            conn.close()
        finally:
            if lock is not None:
                lock.release()


@contextmanager
def transaction(conn: sqlite3.Connection, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE / COMMIT / ROLLBACK wrapper.

    On exception we ROLLBACK and re-raise. We narrow the swallowed exception
    to the "no transaction is active" sqlite OperationalError — anything else
    (locked DB, disk full, etc.) propagates so the original failure isn't masked.
    """
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError as rollback_err:
            if "no transaction is active" not in str(rollback_err).lower():
                log.warning("ROLLBACK raised an unexpected error: %s", rollback_err)
                # Don't re-raise here — the original exception is the real cause
                # and we MUST re-raise it below.
        raise
