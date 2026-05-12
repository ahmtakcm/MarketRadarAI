import pytest

from core.market_data_service import MexcMarketDataService


def test_market_data_service_rejects_unresolved_alias_symbol(monkeypatch):
    service = MexcMarketDataService()

    monkeypatch.setattr(
        "core.market_data_service.exchange_client.fetch_klines",
        lambda *_args: [],
    )

    with pytest.raises(ValueError):
        service.fetch_klines("TSLA", "15m", 10)


def test_market_data_service_does_not_normalize_user_input(monkeypatch):
    service = MexcMarketDataService()

    monkeypatch.setattr(
        "core.market_data_service.exchange_client.fetch_klines",
        lambda *_args: [],
    )

    with pytest.raises(ValueError):
        service.fetch_klines(" btcusdt ", "15m", 10)


def test_market_data_service_delegates_resolved_symbol_without_rewriting(monkeypatch):
    calls = []
    service = MexcMarketDataService()

    monkeypatch.setattr(
        "core.market_data_service.exchange_client.fetch_klines",
        lambda *args: calls.append(args) or [{"close": 1.0}],
    )

    assert service.fetch_klines("TESLAUSDT", "15m", 10) == [{"close": 1.0}]
    assert calls == [("TESLAUSDT", "15m", 10)]
