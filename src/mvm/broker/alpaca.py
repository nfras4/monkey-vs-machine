"""Alpaca paper broker — STUB ONLY. Not wired in v1.

Every method raises NotImplementedError. v2 will fill these in against
the Alpaca paper-trading API. Credentials must live in
`/etc/openclaw/secrets.env`, never in the repo.
"""
from __future__ import annotations

from typing import List, Literal

from .base import AccountSnapshot, Broker, OrderResult, Position


class AlpacaPaperBroker(Broker):
    family = "alpaca_paper"

    def __init__(self, *, key_id: str | None = None, secret: str | None = None, base_url: str | None = None) -> None:
        # Accept credentials but do nothing with them yet — the constructor
        # exists so callers can dependency-inject in v2 without breaking v1.
        self._key_id = key_id
        self._secret = secret
        self._base_url = base_url

    def submit_order(self, symbol: str, qty: float, side: Literal["buy", "sell"]) -> OrderResult:
        raise NotImplementedError("Alpaca wiring is v2 scope; v1 is simulation-only.")

    def get_positions(self) -> List[Position]:
        raise NotImplementedError("Alpaca wiring is v2 scope; v1 is simulation-only.")

    def get_account(self) -> AccountSnapshot:
        raise NotImplementedError("Alpaca wiring is v2 scope; v1 is simulation-only.")
