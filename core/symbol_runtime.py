import logging

from config import REQUESTED_SYMBOLS
from core.exchange_client import validate_futures_symbol
from remote_config import load_config


DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        symbol = str(value or "").upper().strip()
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def configured_scan_symbols():
    cfg = load_config()
    symbols = safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    source = "remote_config.watchlist.symbols"

    if not symbols:
        symbols = safe_symbols(REQUESTED_SYMBOLS)
        source = "settings.json symbols"

    if not symbols:
        symbols = list(DEFAULT_SYMBOLS)
        source = "hardcoded fallback"

    logging.info("Watchlist sembolleri: %s | kaynak=%s", ", ".join(symbols), source)
    return symbols, source


def validate_scan_symbols(symbols, tf="15m", min_candles=30):
    valid = []
    invalid = []

    for symbol in safe_symbols(symbols):
        ok, reason = validate_futures_symbol(symbol, tf=tf, min_candles=min_candles)
        if ok:
            valid.append(symbol)
        else:
            invalid.append((symbol, reason))
            logging.warning("Watchlist sembolu gecersiz; atlandi | %s | %s", symbol, reason)

    return valid, invalid
