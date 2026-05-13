from __future__ import annotations

import logging

from remote_config import load_config
from telegram.api import send_to_chat
from telegram.command_controls import (
    handle_filter_toggle,
    handle_filters,
    handle_modes,
    handle_restart,
    handle_scalp_toggle,
    handle_scan_now,
    restart_process,
)
from telegram.command_reports import (
    handle_error_log,
    handle_health,
    handle_help,
    handle_log,
    handle_performance_today,
    handle_status,
)
from telegram.command_watchlist import handle_add_symbol, handle_remove_symbol, handle_watchlist
from telegram.guards import ADMIN_PRIVATE_COMMANDS, GROUP_SAFE_COMMANDS, check_command_access

__all__ = ["handle_command_message", "restart_process"]


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
        handle_help(reply)
        return
    if cmd == "/health":
        handle_health(reply)
        return
    if cmd == "/status":
        handle_status(reply)
        return
    if cmd == "/scan_now":
        handle_scan_now(reply)
        return
    if cmd == "/restart":
        handle_restart(reply)
        return
    if cmd == "/modes":
        handle_modes(cfg, reply)
        return
    if cmd in ["/scalp_on", "/scalp_off"]:
        handle_scalp_toggle(cmd, reply)
        return
    if cmd == "/filters":
        handle_filters(cfg, reply)
        return
    if cmd in ["/fake_filter_on", "/fake_filter_off", "/volume_filter_on", "/volume_filter_off"]:
        handle_filter_toggle(cmd, reply)
        return
    if cmd == "/watchlist":
        handle_watchlist(cfg, reply)
        return
    if cmd == "/add_symbol":
        handle_add_symbol(parts, reply)
        return
    if cmd == "/remove_symbol":
        handle_remove_symbol(parts, reply)
        return
    if cmd == "/performance_today":
        handle_performance_today(reply)
        return
    if cmd == "/log":
        handle_log(reply)
        return
    if cmd == "/error_log":
        handle_error_log(reply)
        return

    reply("Bilinmeyen komut. /help yaz.")
