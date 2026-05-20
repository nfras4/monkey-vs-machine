"""Asserts the broker stub has the v2-ready shape and raises NotImplementedError."""
from __future__ import annotations

import pytest

from mvm.broker.alpaca import AlpacaPaperBroker
from mvm.broker.base import Broker


def test_alpaca_paper_is_a_broker():
    b = AlpacaPaperBroker()
    assert isinstance(b, Broker)


def test_methods_exist_and_raise_not_implemented():
    b = AlpacaPaperBroker()
    with pytest.raises(NotImplementedError):
        b.submit_order("AAPL", 1, "buy")
    with pytest.raises(NotImplementedError):
        b.get_positions()
    with pytest.raises(NotImplementedError):
        b.get_account()
