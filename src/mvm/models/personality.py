"""Typed Personality dataclasses for the 8 named-monkey cast.

Persisted form: JSON config in `named_monkeys.personality_config` (D1-friendly).
Tick-time form: parse JSON -> typed Personality subclass at tick start.
Dispatcher uses `match` so adding a new archetype requires updating all
relevant match arms or raising at parse time (no silent fall-throughs).

Two kinds of behaviour:
- `decide(...)` — overrides the trade decision for this monkey on this day.
  Returns a Decision: hold / sell / buy(ticker_idx).
  Personalities that don't affect trades (LakersFan, Babysitter) inherit
  the base Personality.decide() which always returns hold.

- `event_adjustment(...)` — a post-tick equity delta (e.g. Joe's $100 Lakers
  bonus, Wendy's $25 Monday babysitting credit). Returns 0.0 by default.

Both methods are pure: no DB writes, no clock reads, no external HTTP.
External data flows in via the `conn` for `event_adjustment` so it can read
the frozen `external_events` table (already fingerprint-guarded at tick start).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timedelta
from typing import Iterable

import numpy as np

# Decision codes match step_monkeys_one_day's action codes.
HOLD = 0
SELL = 1
BUY = 2


@dataclass
class Decision:
    action: int  # HOLD / SELL / BUY
    ticker_idx: int = -1  # used only for BUY; -1 otherwise


# Base class. Trading-affecting personalities override `decide`; event-driven
# ones (LakersFan, Babysitter) leave `affects_trades=False` so the override
# pass leaves their vector-path decisions intact.
@dataclass
class Personality:
    kind: str
    # When False, the personality only contributes via event_adjustment and
    # the vector-path trade decision for that monkey is kept as-is.
    affects_trades: bool = True

    def decide(
        self,
        rng: np.random.Generator,
        date: str,
        close_filled,  # pd.DataFrame
        universe: list[str],
        current_pos_idx: int,
        has_pos: bool,
    ) -> Decision:
        return Decision(HOLD)

    def event_adjustment(self, date: str, conn: sqlite3.Connection) -> float:
        return 0.0


@dataclass
class TechLover(Personality):
    tickers: list[str] = field(default_factory=list)
    bias: float = 0.7
    p_trade: float = 0.05
    p_sell: float = 0.5

    def decide(self, rng, date, close_filled, universe, current_pos_idx, has_pos):
        if rng.random() >= self.p_trade:
            return Decision(HOLD)
        if has_pos and rng.random() < self.p_sell:
            return Decision(SELL)
        if not has_pos:
            # Bias toward the tech whitelist
            tech_idxs = [universe.index(t) for t in self.tickers if t in universe]
            if tech_idxs and rng.random() < self.bias:
                return Decision(BUY, int(rng.choice(tech_idxs)))
            return Decision(BUY, int(rng.integers(0, len(universe))))
        return Decision(HOLD)


@dataclass
class ValueHunter(Personality):
    tickers: list[str] = field(default_factory=list)
    bias: float = 0.7
    p_trade: float = 0.05
    p_sell: float = 0.5
    max_tech_hold_days: int = 5
    tech_blacklist: list[str] = field(default_factory=list)

    def decide(self, rng, date, close_filled, universe, current_pos_idx, has_pos):
        # Force-sell if currently holding a blacklisted tech ticker.
        if has_pos and 0 <= current_pos_idx < len(universe):
            if universe[current_pos_idx] in self.tech_blacklist:
                return Decision(SELL)
        if rng.random() >= self.p_trade:
            return Decision(HOLD)
        if has_pos and rng.random() < self.p_sell:
            return Decision(SELL)
        if not has_pos:
            value_idxs = [universe.index(t) for t in self.tickers if t in universe]
            if value_idxs and rng.random() < self.bias:
                return Decision(BUY, int(rng.choice(value_idxs)))
            # Even on the non-bias roll, never buy a blacklisted ticker.
            ok = [i for i, t in enumerate(universe) if t not in self.tech_blacklist]
            if ok:
                return Decision(BUY, int(rng.choice(ok)))
        return Decision(HOLD)


@dataclass
class WeekdayTrader(Personality):
    """Only trades on `trade_days` (0=Mon..6=Sun). Higher trade_prob to compensate."""
    trade_days: list[int] = field(default_factory=lambda: [0])
    trade_prob: float = 0.3
    p_sell: float = 0.5

    def decide(self, rng, date, close_filled, universe, current_pos_idx, has_pos):
        dow = date_cls.fromisoformat(date).weekday()
        if dow not in self.trade_days:
            return Decision(HOLD)
        if rng.random() >= self.trade_prob:
            return Decision(HOLD)
        if has_pos and rng.random() < self.p_sell:
            return Decision(SELL)
        if not has_pos:
            return Decision(BUY, int(rng.integers(0, len(universe))))
        return Decision(HOLD)


@dataclass
class ContrarianWeekday(Personality):
    """Buys only on `buy_days`, sells only on `sell_days`. No randomness — pure schedule."""
    buy_days: list[int] = field(default_factory=lambda: [0])
    sell_days: list[int] = field(default_factory=lambda: [4])

    def decide(self, rng, date, close_filled, universe, current_pos_idx, has_pos):
        dow = date_cls.fromisoformat(date).weekday()
        if has_pos and dow in self.sell_days:
            return Decision(SELL)
        if not has_pos and dow in self.buy_days:
            return Decision(BUY, int(rng.integers(0, len(universe))))
        return Decision(HOLD)


@dataclass
class DipBuyer(Personality):
    """Only buys when last close < close `lookback` days ago by >= |threshold|."""
    lookback: int = 3
    threshold: float = -0.02
    p_sell: float = 0.05

    def decide(self, rng, date, close_filled, universe, current_pos_idx, has_pos):
        # Sell rarely; never force-sell.
        if has_pos and rng.random() < self.p_sell:
            return Decision(SELL)
        if has_pos:
            return Decision(HOLD)
        # Buying: need a market-wide dip signal. Use mean ticker return as the index.
        import pandas as pd
        today_ts = pd.to_datetime(date)
        if today_ts not in close_filled.index:
            return Decision(HOLD)
        ago = close_filled.index[close_filled.index <= today_ts]
        if len(ago) < self.lookback + 1:
            return Decision(HOLD)
        prev_ts = ago[-(self.lookback + 1)]
        ret = (close_filled.loc[today_ts] / close_filled.loc[prev_ts] - 1.0).mean()
        if ret > self.threshold:
            return Decision(HOLD)  # not enough of a dip
        return Decision(BUY, int(rng.integers(0, len(universe))))


@dataclass
class MomentumChaser(Personality):
    """Buys top-momentum ticker; sells held ticker on >= |sell_threshold| drawdown."""
    lookback: int = 5
    buy_threshold: float = 0.05
    sell_threshold: float = -0.05

    def decide(self, rng, date, close_filled, universe, current_pos_idx, has_pos):
        import pandas as pd
        today_ts = pd.to_datetime(date)
        if today_ts not in close_filled.index:
            return Decision(HOLD)
        idx = close_filled.index[close_filled.index <= today_ts]
        if len(idx) < self.lookback + 1:
            return Decision(HOLD)
        prev_ts = idx[-(self.lookback + 1)]
        rets = (close_filled.loc[today_ts] / close_filled.loc[prev_ts] - 1.0)

        if has_pos and 0 <= current_pos_idx < len(universe):
            held_ticker = universe[current_pos_idx]
            r = float(rets.get(held_ticker, 0.0))
            if r <= self.sell_threshold:
                return Decision(SELL)
            return Decision(HOLD)
        # No position: buy the top-momentum ticker if it's above buy_threshold.
        rets_sorted = rets.sort_values(ascending=False)
        if rets_sorted.empty:
            return Decision(HOLD)
        top_ticker = rets_sorted.index[0]
        top_ret = float(rets_sorted.iloc[0])
        if top_ret < self.buy_threshold:
            return Decision(HOLD)
        return Decision(BUY, universe.index(top_ticker))


@dataclass
class LakersFan(Personality):
    """No trade override — pure event-driven equity adjustment."""
    affects_trades: bool = False
    event_kind: str = "lakers_game"
    win_bonus: float = 100.0
    loss_penalty: float = -50.0
    floor: float = 0.0

    def event_adjustment(self, date: str, conn: sqlite3.Connection) -> float:
        row = conn.execute(
            "SELECT outcome FROM external_events WHERE date=? AND event_kind=?",
            (date, self.event_kind),
        ).fetchone()
        if row is None:
            return 0.0
        # outcome is 1 (win) or 0 (loss). Anything else -> 0.
        outcome = row["outcome"] if hasattr(row, "keys") else row[0]
        if outcome == 1:
            return float(self.win_bonus)
        if outcome == 0:
            return float(self.loss_penalty)
        return 0.0


@dataclass
class Babysitter(Personality):
    """Deterministic Monday credit (Saturday's gig pays out the following Monday)."""
    affects_trades: bool = False
    credit_amount: float = 25.0
    credit_day: int = 0  # Monday

    def event_adjustment(self, date: str, conn: sqlite3.Connection) -> float:
        dow = date_cls.fromisoformat(date).weekday()
        return float(self.credit_amount) if dow == self.credit_day else 0.0


# Registry mapping kind string -> class. Used by both the dispatcher and tests.
PERSONALITY_REGISTRY: dict[str, type[Personality]] = {
    "tech_lover": TechLover,
    "value_hunter": ValueHunter,
    "weekday_trader": WeekdayTrader,
    "contrarian_weekday": ContrarianWeekday,
    "dip_buyer": DipBuyer,
    "momentum_chaser": MomentumChaser,
    "lakers_fan": LakersFan,
    "babysitter": Babysitter,
}


def from_config(config: dict | str) -> Personality:
    """Parse a stored JSON config (string or dict) into a typed Personality.

    Raises ValueError on unknown `kind` rather than silently constructing a
    no-op personality — protects against typos in DB rows.
    """
    if isinstance(config, str):
        config = json.loads(config)
    kind = config.get("kind")
    if not kind:
        raise ValueError(f"personality_config missing 'kind': {config}")
    cls = PERSONALITY_REGISTRY.get(kind)
    if cls is None:
        raise ValueError(f"Unknown personality kind: {kind!r}. Known: {list(PERSONALITY_REGISTRY)}")
    # Strip 'kind' from config; remaining keys must match dataclass fields.
    payload = {k: v for k, v in config.items() if k != "kind"}
    return cls(kind=kind, **payload)


def load_named_personalities(conn: sqlite3.Connection) -> dict[int, tuple[str, Personality]]:
    """Read named_monkeys WHERE personality_config IS NOT NULL.

    Returns {monkey_id: (name, Personality)}. Rows with category != 'personality'
    are ignored — those are daily-refreshed slots (top/bottom/mover) that don't
    have configs.
    """
    rows = conn.execute(
        """
        SELECT monkey_id, name, personality_config
        FROM named_monkeys
        WHERE category='personality' AND personality_config IS NOT NULL
        ORDER BY monkey_id
        """
    ).fetchall()
    out: dict[int, tuple[str, Personality]] = {}
    for r in rows:
        mid = int(r["monkey_id"] if hasattr(r, "keys") else r[0])
        name = r["name"] if hasattr(r, "keys") else r[1]
        cfg = r["personality_config"] if hasattr(r, "keys") else r[2]
        out[mid] = (name, from_config(cfg))
    return out
