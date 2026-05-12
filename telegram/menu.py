from __future__ import annotations

import json
import logging

from telegram.api import tg
from telegram.settings import ADMIN_CHAT_ID, GROUP_CHAT_ID

BOTFATHER_COMMANDS = [
    ("help", "Komut listesi"),
    ("health", "Sistem sagligi"),
    ("status", "Bot durumu"),
    ("scan_now", "Anlik tarama"),
    ("restart", "Bot process restart"),
    ("modes", "Mod durumu"),
    ("scalp_on", "Scalp ac"),
    ("scalp_off", "Scalp kapat"),
    ("filters", "Filtre durumu"),
    ("fake_filter_on", "Fake filtre ac"),
    ("fake_filter_off", "Fake filtre kapat"),
    ("volume_filter_on", "Volume filtre ac"),
    ("volume_filter_off", "Volume filtre kapat"),
    ("watchlist", "Izleme listesi"),
    ("add_symbol", "Sembol ekle"),
    ("remove_symbol", "Sembol cikar"),
    ("performance_today", "Gunluk performans"),
    ("log", "Son loglar"),
    ("error_log", "Hata loglari"),
]

_commands_synced = False


def sync_telegram_commands() -> None:
    global _commands_synced
    if _commands_synced:
        return

    commands = [
        {"command": command, "description": description}
        for command, description in BOTFATHER_COMMANDS
    ]

    tg(
        "setMyCommands",
        commands=json.dumps(commands, ensure_ascii=False),
        scope=json.dumps({"type": "chat", "chat_id": int(ADMIN_CHAT_ID)}),
    )

    tg(
        "setMyCommands",
        commands="[]",
        scope=json.dumps({"type": "chat", "chat_id": int(GROUP_CHAT_ID)}),
    )

    _commands_synced = True
    logging.info("Telegram command menu synced")
