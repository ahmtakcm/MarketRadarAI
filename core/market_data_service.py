from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core import exchange_client


class MarketDataService(Protocol):
    def fetch_klines(self, symbol: str, interval: str, limit: int):
        """Fetch candles for an already-resolved exchange symbol."""

    def get_kline_limit(self, interval: str) -> int:
        """Return candle limit for a scanner timeframe."""

    def get_valid_futures_symbols(self) -> list[str]:
        """Return active exchange symbols in scanner format."""


def _require_resolved_exchange_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise TypeError("MarketDataService requires a resolved exchange symbol string")
    if symbol != symbol.strip() or symbol != symbol.upper() or not symbol.endswith("USDT"):
        raise ValueError(
            "MarketDataService accepts only already-resolved uppercase exchange symbols"
        )
    return symbol


@dataclass(frozen=True)
class MexcMarketDataService:
    def fetch_klines(self, symbol: str, interval: str, limit: int):
        return exchange_client.fetch_klines(_require_resolved_exchange_symbol(symbol), interval, limit)

    def get_kline_limit(self, interval: str) -> int:
        return exchange_client.get_kline_limit(interval)

    def get_valid_futures_symbols(self) -> list[str]:
        return exchange_client.get_valid_futures_symbols()


DEFAULT_MARKET_DATA_SERVICE = MexcMarketDataService()


def fetch_klines(symbol: str, interval: str, limit: int):
    return DEFAULT_MARKET_DATA_SERVICE.fetch_klines(symbol, interval, limit)


def get_kline_limit(interval: str) -> int:
    return DEFAULT_MARKET_DATA_SERVICE.get_kline_limit(interval)


def get_valid_futures_symbols() -> list[str]:
    return DEFAULT_MARKET_DATA_SERVICE.get_valid_futures_symbols()
