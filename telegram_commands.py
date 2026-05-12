"""Backward-compatible Telegram runtime facade.

Runtime code and existing tests import this module. The implementation now
lives in the `telegram` package so polling, guards, handlers, menu sync, offset
persistence, and formatting have explicit ownership.
"""

from __future__ import annotations

from telegram.api import requests
from telegram.api import send_to_chat as _send_to_chat
from telegram.api import tg as _tg
from telegram.dispatcher import poll_telegram_commands
from telegram.guards import ADMIN_PRIVATE_COMMANDS, GROUP_SAFE_COMMANDS
from telegram.handlers import handle_command_message
from telegram.handlers import restart_process as _restart_process
from telegram.menu import BOTFATHER_COMMANDS, sync_telegram_commands
from telegram.messages import (
    build_status,
)
from telegram.messages import (
    help_text as _help_text,
)
from telegram.messages import (
    read_tail as _read_tail,
)
from telegram.messages import (
    watchlist_text as _watchlist_text,
)
from telegram.settings import (
    ADMIN_CHAT_ID,
    ALLOWED_CHAT_ID,
    API,
    BASE_DIR,
    BOT_TOKEN,
    GROUP_CHAT_ID,
)

__all__ = [
    "ADMIN_CHAT_ID",
    "ADMIN_PRIVATE_COMMANDS",
    "ALLOWED_CHAT_ID",
    "API",
    "BASE_DIR",
    "BOTFATHER_COMMANDS",
    "BOT_TOKEN",
    "GROUP_CHAT_ID",
    "GROUP_SAFE_COMMANDS",
    "_help_text",
    "_read_tail",
    "_restart_process",
    "_send_to_chat",
    "_tg",
    "_watchlist_text",
    "build_status",
    "handle_command_message",
    "poll_telegram_commands",
    "requests",
    "sync_telegram_commands",
]
