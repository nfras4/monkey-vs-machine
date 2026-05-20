from __future__ import annotations

from mvm.state.hash_seed import hash_seed


def test_hash_seed_is_stable():
    a = hash_seed("ai_train", "hgb_v1", "2026-05-18", seed_string="mvm-genesis-2026-05-15")
    b = hash_seed("ai_train", "hgb_v1", "2026-05-18", seed_string="mvm-genesis-2026-05-15")
    assert a == b


def test_hash_seed_changes_with_args():
    a = hash_seed("ai_train", "hgb_v1", "2026-05-18")
    b = hash_seed("ai_train", "hgb_v1", "2026-05-19")
    assert a != b


def test_hash_seed_returns_uint64_range():
    s = hash_seed("monkey_tick", "2026-05-18")
    assert 0 <= s < (1 << 64)
