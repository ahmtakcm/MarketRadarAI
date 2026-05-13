from __future__ import annotations

import logging

from core.market_data_service import get_valid_futures_symbols
from core.symbol_resolver import SymbolResolver
from remote_config import normalize_symbol, update_config
from telegram.messages import watchlist_text


def handle_watchlist(cfg, reply) -> None:
    reply(watchlist_text(cfg))


def handle_add_symbol(parts: list[str], reply) -> None:
    if len(parts) < 2:
        reply("KullanÄ±m: /add_symbol BTCUSDT")
        return

    symbol = normalize_symbol(parts[1])

    try:
        valid_symbols = set(get_valid_futures_symbols())
    except Exception as e:
        logging.exception("Sembol doÄŸrulama hatasÄ±")
        reply(f"âŒ Borsa sembol listesi alÄ±namadÄ±. Daha sonra tekrar dene. Hata: {str(e)[:120]}")
        return

    resolution = SymbolResolver().resolve(symbol, valid_symbols)
    if not resolution.supported or not resolution.resolved:
        reply(
            f"âŒ Sembol eklenmedi: {symbol}\n"
            "Bu Ã§ift gÃ¼ncel futures listesinde gÃ¶rÃ¼nmÃ¼yor."
        )
        return

    resolved_symbol = resolution.resolved
    result = {"already_present": False}

    def add_symbol(current):
        symbols = current.setdefault("watchlist", {}).setdefault("symbols", [])
        if resolved_symbol in symbols:
            result["already_present"] = True
            return
        symbols.append(resolved_symbol)

    update_config(add_symbol)

    if result["already_present"]:
        reply(f"â„¹ï¸ Sembol zaten listede: {resolved_symbol}")
        return

    if resolved_symbol != symbol:
        reply(f"âœ… Sembol eklendi: {symbol} -> {resolved_symbol}")
    else:
        reply(f"âœ… Sembol eklendi: {resolved_symbol}")


def handle_remove_symbol(parts: list[str], reply) -> None:
    if len(parts) < 2:
        reply("KullanÃ„Â±m: /remove_symbol BTCUSDT")
        return
    symbol = normalize_symbol(parts[1])

    def remove_symbol(current):
        current.setdefault("watchlist", {}).setdefault("symbols", [])
        current["watchlist"]["symbols"] = [
            item for item in current["watchlist"]["symbols"] if item != symbol
        ]

    update_config(remove_symbol)
    reply(f"ÄŸÅ¸â€”â€˜ Sembol ÃƒÂ§Ã„Â±karÃ„Â±ldÃ„Â±: {symbol}")
