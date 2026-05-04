from __future__ import annotations

from core.exchange_client import validate_futures_symbol
from remote_config import save_config


def safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        symbol = str(value or "").upper().strip()
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def watchlist_status_text(cfg):
    symbols = safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    if not symbols:
        return "WATCHLIST\n\nWatchlist bos."

    lines = ["WATCHLIST", ""]
    for symbol in symbols:
        ok, reason = validate_futures_symbol(symbol)
        status = "valid" if ok else f"invalid: {reason}"
        lines.append(f"{symbol}: {status}")

    return "\n".join(lines)


def add_symbol(cfg, symbol: str) -> str:
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        return "Kullanim: /addsymbol BTCUSDT"

    ok, reason = validate_futures_symbol(symbol)
    if not ok:
        return f"Sembol eklenmedi: {symbol}\nNeden: {reason}"

    watchlist = cfg.setdefault("watchlist", {}).setdefault("symbols", [])
    existing = safe_symbols(watchlist)
    if symbol in existing:
        return f"Sembol zaten watchlist icinde: {symbol}"

    existing.append(symbol)
    cfg["watchlist"]["symbols"] = existing
    cfg["watchlist"]["watched_symbols"] = existing
    save_config(cfg)
    return f"Sembol watchlist'e eklendi: {symbol}"


def remove_symbol(cfg, symbol: str) -> str:
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        return "Kullanim: /removesymbol BTCUSDT"

    existing = safe_symbols(cfg.setdefault("watchlist", {}).setdefault("symbols", []))
    if symbol not in existing:
        return f"Sembol watchlist icinde yok: {symbol}"

    updated = [item for item in existing if item != symbol]
    cfg["watchlist"]["symbols"] = updated
    cfg["watchlist"]["watched_symbols"] = updated
    save_config(cfg)
    return f"Sembol watchlist'ten silindi: {symbol}"
