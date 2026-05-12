from __future__ import annotations

import logging
import os
import sys
import threading

from core.market_data_service import get_valid_futures_symbols
from core.symbol_resolver import SymbolResolver
from remote_config import get_active_modes, load_config, normalize_symbol, update_config
from telegram.api import send_to_chat
from telegram.guards import ADMIN_PRIVATE_COMMANDS, GROUP_SAFE_COMMANDS, check_command_access
from telegram.messages import (
    build_health_text,
    build_performance_today_text,
    build_status,
    error_log_text,
    help_text,
    log_text,
    watchlist_text,
)


def restart_process(delay_seconds=1.5):
    def do_restart():
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Timer(delay_seconds, do_restart).start()


def set_config_value(section: str, key: str, value) -> None:
    def mutate(current):
        current.setdefault(section, {})[key] = value

    update_config(mutate)


def handle_command_message(message, send_telegram):
    access = check_command_access(message)

    if not access.is_admin_private and not access.is_group_chat:
        logging.warning("Yetkisiz Telegram mesaj reddedildi: chat_id=%s", access.chat_id)
        return

    if access.is_group_chat and access.command not in GROUP_SAFE_COMMANDS:
        logging.warning(
            "Group-safe olmayan komut reddedildi: chat_id=%s cmd=%s",
            access.chat_id,
            access.command,
        )
        return

    cfg = load_config()

    def reply(reply_text: str) -> None:
        send_to_chat(access.chat_id, reply_text)

    text = message.get("text", "").strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = access.command

    if access.is_admin_private and cmd not in ADMIN_PRIVATE_COMMANDS:
        logging.warning("Admin registry disi komut reddedildi: chat_id=%s cmd=%s", access.chat_id, cmd)
        reply("Bilinmeyen komut. /help yaz.")
        return

    if cmd == "/help":
        reply(help_text())
        return

    if cmd == "/health":
        reply(build_health_text())
        return

    if cmd == "/status":
        reply(build_status())
        return

    if cmd == "/scan_now":
        set_config_value("runtime", "force_scan_once", True)
        reply("Anlik tarama tetiklendi. Aktif modlar icin mum kapanisi beklenmeden tarama baslatiliyor.")
        return

    if cmd == "/restart":
        reply("Bot process yeniden baslatiliyor...")
        restart_process()
        return

    if cmd == "/modes":
        active_modes = get_active_modes(cfg)
        reply(
            "MODLAR\n\n"
            f"Scalp: {'ON' if cfg['modes'].get('scalp') else 'OFF'}\n"
            f"Intraday: {'ON' if cfg['modes'].get('intraday') else 'OFF'}\n"
            f"Midterm: {'ON' if cfg['modes'].get('midterm') else 'OFF'}\n\n"
            f"Aktif calisan: {', '.join(active_modes) or 'Yok'}\n"
            "Not: /scan_now aktif modlari anlik tarar."
        )
        return

    if cmd in ["/scalp_on", "/scalp_off"]:
        state = cmd.strip("/").split("_")[1]
        set_config_value("modes", "scalp", state == "on")
        reply(f"Scalp mode {'enabled' if state == 'on' else 'disabled'}.")
        return

    if cmd == "/filters":
        reply(
            "FILTRELER\n\n"
            f"Fake breakout: {'ON' if cfg['filters'].get('fake_breakout_filter') else 'OFF'}\n"
            f"Volume: {'ON' if cfg['filters'].get('volume_confirmation') else 'OFF'}"
        )
        return

    if cmd == "/fake_filter_on":
        set_config_value("filters", "fake_breakout_filter", True)
        reply("Fake breakout filtresi acildi.")
        return

    if cmd == "/fake_filter_off":
        set_config_value("filters", "fake_breakout_filter", False)
        reply("Fake breakout filtresi kapatildi.")
        return

    if cmd == "/volume_filter_on":
        set_config_value("filters", "volume_confirmation", True)
        reply("Volume filtresi acildi.")
        return

    if cmd == "/volume_filter_off":
        set_config_value("filters", "volume_confirmation", False)
        reply("Volume filtresi kapatildi.")
        return

    if cmd == "/watchlist":
        reply(watchlist_text(cfg))
        return

    if cmd == "/add_symbol":
        if len(parts) < 2:
            reply("Kullanım: /add_symbol BTCUSDT")
            return

        symbol = normalize_symbol(parts[1])

        try:
            valid_symbols = set(get_valid_futures_symbols())
        except Exception as e:
            logging.exception("Sembol doğrulama hatası")
            reply(f"❌ Borsa sembol listesi alınamadı. Daha sonra tekrar dene. Hata: {str(e)[:120]}")
            return

        resolution = SymbolResolver().resolve(symbol, valid_symbols)
        if not resolution.supported or not resolution.resolved:
            reply(
                f"❌ Sembol eklenmedi: {symbol}\n"
                "Bu çift güncel futures listesinde görünmüyor."
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
            reply(f"ℹ️ Sembol zaten listede: {resolved_symbol}")
            return

        if resolved_symbol != symbol:
            reply(f"✅ Sembol eklendi: {symbol} -> {resolved_symbol}")
        else:
            reply(f"✅ Sembol eklendi: {resolved_symbol}")
        return

    if cmd == "/remove_symbol":
        if len(parts) < 2:
            reply("KullanÄ±m: /remove_symbol BTCUSDT")
            return
        symbol = normalize_symbol(parts[1])

        def remove_symbol(current):
            current.setdefault("watchlist", {}).setdefault("symbols", [])
            current["watchlist"]["symbols"] = [
                item for item in current["watchlist"]["symbols"] if item != symbol
            ]

        update_config(remove_symbol)
        reply(f"ğŸ—‘ Sembol Ã§Ä±karÄ±ldÄ±: {symbol}")
        return

    if cmd == "/performance_today":
        reply(build_performance_today_text())
        return

    if cmd == "/log":
        reply(log_text())
        return

    if cmd == "/error_log":
        reply(error_log_text())
        return

    reply("Bilinmeyen komut. /help yaz.")
