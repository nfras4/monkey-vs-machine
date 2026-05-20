"""Pure stepper is deterministic given a fixed RNG."""
from __future__ import annotations

import numpy as np

from mvm.models.monkey_step import compute_equity, step_monkeys_one_day


def _initial_state(n=100, k=5, starting_cash=10_000.0):
    cash = np.full(n, starting_cash, dtype=np.float64)
    shares = np.zeros(n, dtype=np.float64)
    pos = np.full(n, -1, dtype=np.int32)
    prices = np.linspace(50, 150, k).astype(np.float64)
    return cash, shares, pos, prices


def test_step_is_deterministic_across_runs():
    cash1, shares1, pos1, prices = _initial_state()
    cash2, shares2, pos2, prices2 = _initial_state()
    rng1 = np.random.default_rng(seed=42)
    rng2 = np.random.default_rng(seed=42)
    a1 = step_monkeys_one_day(prices, cash1, shares1, pos1, rng=rng1)
    a2 = step_monkeys_one_day(prices2, cash2, shares2, pos2, rng=rng2)
    np.testing.assert_array_equal(cash1, cash2)
    np.testing.assert_array_equal(shares1, shares2)
    np.testing.assert_array_equal(pos1, pos2)
    np.testing.assert_array_equal(a1, a2)


def test_equity_with_no_positions_equals_cash():
    cash, shares, pos, prices = _initial_state()
    eq = compute_equity(prices, cash, shares, pos)
    np.testing.assert_array_equal(eq, cash)
