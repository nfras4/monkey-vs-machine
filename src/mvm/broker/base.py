"""Broker interface — abstract base for real-broker integration in v2."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Literal


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    symbol: str
    qty: float
    side: Literal["buy", "sell"]
    filled_avg_price: float | None = None
    status: str = "submitted"


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float


@dataclass(frozen=True)
class AccountSnapshot:
    cash: float
    equity: float
    buying_power: float
    pattern_day_trader: bool = False


class Broker(ABC):
    """Minimal broker interface. v2 will implement against Alpaca paper trading."""

    @abstractmethod
    def submit_order(self, symbol: str, qty: float, side: Literal["buy", "sell"]) -> OrderResult:
        ...

    @abstractmethod
    def get_positions(self) -> List[Position]:
        ...

    @abstractmethod
    def get_account(self) -> AccountSnapshot:
        ...
