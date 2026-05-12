import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.asset_universe import (
    build_watchlist_text,
    format_asset_resolution_log,
    resolve_asset_universe,
)


def test_asset_universe_splits_supported_and_unsupported_symbols():
    resolution = resolve_asset_universe(
        ["btcusdt", "ETHUSDT", "AAPLUSDT", "BTCUSDT", ""],
        ["BTCUSDT", "ETHUSDT"],
    )

    assert resolution.requested == ["BTCUSDT", "ETHUSDT", "AAPLUSDT"]
    assert resolution.supported == ["BTCUSDT", "ETHUSDT"]
    assert resolution.unsupported == ["AAPLUSDT"]
    assert resolution.supported_count == 2
    assert resolution.unsupported_count == 1


def test_asset_universe_log_and_watchlist_text_are_marketradarai_visible():
    resolution = resolve_asset_universe(
        ["BTCUSDT", "AAPLUSDT", "XAUUSDT"],
        ["BTCUSDT"],
    )

    assert format_asset_resolution_log(resolution) == (
        "MarketRadarAI asset universe | exchange=MEXC | requested=3 | supported=1 | unsupported=2"
    )

    text = build_watchlist_text(resolution)
    assert "MarketRadarAI WATCHLIST" in text
    assert "Taranacak semboller:" in text
    assert "BTCUSDT" in text
    assert "Desteklenmeyen semboller:" in text
    assert "AAPLUSDT, XAUUSDT" in text
