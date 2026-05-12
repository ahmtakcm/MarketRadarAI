import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.symbol_resolver import SymbolResolver


def test_symbol_resolver_keeps_exact_valid_symbol():
    resolver = SymbolResolver()
    result = resolver.resolve("btcusdt", {"BTCUSDT"})

    assert result.requested == "BTCUSDT"
    assert result.resolved == "BTCUSDT"
    assert result.supported is True
    assert result.reason == "exact"


def test_symbol_resolver_maps_known_display_symbols_to_mexc_symbols():
    resolver = SymbolResolver()
    valid_symbols = {
        "XAUTUSDT",
        "SILVERUSDT",
        "UKOILUSDT",
        "USOILUSDT",
        "SPX500USDT",
        "QQQSTOCKUSDT",
        "TESLAUSDT",
        "NVIDIAUSDT",
        "HK50USDT",
    }

    cases = {
        "GOLD(XAUT)USDT": "XAUTUSDT",
        "SILVER(XAG)USDT": "SILVERUSDT",
        "OIL(BRENT)USDT": "UKOILUSDT",
        "OIL(WTI)USDT": "USOILUSDT",
        "SP500USDT": "SPX500USDT",
        "QQQUSDT": "QQQSTOCKUSDT",
        "TSLAUSDT": "TESLAUSDT",
        "NVDAUSDT": "NVIDIAUSDT",
        "HK50": "HK50USDT",
    }

    for requested, expected in cases.items():
        result = resolver.resolve(requested, valid_symbols)
        assert result.resolved == expected
        assert result.supported is True
        assert result.reason == "alias"


def test_symbol_resolver_keeps_unknown_symbol_unsupported():
    resolver = SymbolResolver()
    result = resolver.resolve("UNKNOWNUSDT", {"BTCUSDT"})

    assert result.requested == "UNKNOWNUSDT"
    assert result.resolved is None
    assert result.supported is False
    assert result.reason == "unsupported"


def test_symbol_resolver_reports_alias_target_missing_when_target_is_not_active():
    resolver = SymbolResolver()
    result = resolver.resolve("TSLAUSDT", {"BTCUSDT"})

    assert result.requested == "TSLAUSDT"
    assert result.resolved is None
    assert result.supported is False
    assert result.reason == "alias_target_missing"


def test_symbol_resolver_preserves_active_alternatives_for_review_aliases():
    resolver = SymbolResolver()
    result = resolver.resolve("GAS(NG)USDT", {"GASUSDT", "NGASUSDT"})

    assert result.resolved == "GASUSDT"
    assert result.supported is True
    assert result.reason == "alias"
    assert result.alternatives == ["NGASUSDT"]


def test_symbol_resolver_matches_common_stock_shortcodes_without_usdt_suffix():
    resolver = SymbolResolver()
    valid_symbols = {"TESLAUSDT", "NVIDIAUSDT"}

    tsla = resolver.resolve("TSLA", valid_symbols)
    nvda = resolver.resolve("NVDA", valid_symbols)

    assert tsla.resolved == "TESLAUSDT"
    assert tsla.supported is True
    assert tsla.reason == "alias"

    assert nvda.resolved == "NVIDIAUSDT"
    assert nvda.supported is True
    assert nvda.reason == "alias"
