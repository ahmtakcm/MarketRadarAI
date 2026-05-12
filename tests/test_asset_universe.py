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

    log = format_asset_resolution_log(resolution)
    assert log.startswith("MarketRadarAI asset universe | exchange=MEXC | requested=3 | supported=1 | unsupported=2")
    assert "resolution_reasons=" in log

    text = build_watchlist_text(resolution)
    assert "MarketRadarAI WATCHLIST" in text
    assert "Summary: MEXC | requested 3 | supported 1 | unsupported 2" in text
    assert "Supported scan symbols:" in text
    assert "BTCUSDT" in text
    assert "Unsupported symbols:" in text
    assert "AAPLUSDT, XAUUSDT" in text

def test_asset_universe_resolves_known_aliases_before_marking_unsupported():
    resolution = resolve_asset_universe(
        ["TSLAUSDT", "SP500USDT", "UNKNOWNUSDT"],
        ["TESLAUSDT", "SPX500USDT"],
    )

    assert resolution.requested == ["TSLAUSDT", "SP500USDT", "UNKNOWNUSDT"]
    assert resolution.supported == ["TESLAUSDT", "SPX500USDT"]
    assert resolution.unsupported == ["UNKNOWNUSDT"]
    assert resolution.resolved_aliases == {
        "TSLAUSDT": "TESLAUSDT",
        "SP500USDT": "SPX500USDT",
    }

    text = build_watchlist_text(resolution)
    assert "Resolved aliases:" in text
    assert "TSLAUSDT -> TESLAUSDT" in text
    assert "SP500USDT -> SPX500USDT" in text


def test_asset_universe_log_includes_symbol_resolution_reason_counts():
    resolution = resolve_asset_universe(
        ["BTCUSDT", "TSLA", "SPX", "UNKNOWNUSDT"],
        ["BTCUSDT", "TESLAUSDT", "SPXUSDT", "SPX500USDT"],
    )

    assert resolution.resolution_reasons == {
        "exact": 1,
        "alias": 1,
        "unsupported": 2,
    }

    log = format_asset_resolution_log(resolution)
    assert "resolution_reasons=exact:1,alias:1,unsupported:2" in log


