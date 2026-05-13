from __future__ import annotations

import os
from pathlib import Path

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

DEFAULT_ADMIN_CHAT_ID = "1218508355"
DEFAULT_GROUP_CHAT_ID = "-1003949299046"


def resolve_chat_ids() -> tuple[str, str, str]:
    admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", DEFAULT_ADMIN_CHAT_ID).strip() or DEFAULT_ADMIN_CHAT_ID
    group_chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID", DEFAULT_GROUP_CHAT_ID).strip() or DEFAULT_GROUP_CHAT_ID
    allowed_chat_id = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()

    if not allowed_chat_id:
        try:
            from config import CHAT_ID as CONFIG_CHAT_ID

            allowed_chat_id = str(CONFIG_CHAT_ID).strip()
        except Exception:
            pass

    if not group_chat_id and allowed_chat_id:
        group_chat_id = allowed_chat_id

    return admin_chat_id, group_chat_id, allowed_chat_id


ADMIN_CHAT_ID, GROUP_CHAT_ID, ALLOWED_CHAT_ID = resolve_chat_ids()

try:
    from notifiers import telegram_notifier as _telegram_sender

    if hasattr(_telegram_sender, "BOT_TOKEN"):
        BOT_TOKEN = _telegram_sender.BOT_TOKEN
    if hasattr(_telegram_sender, "CHAT_ID"):
        CHAT_ID = _telegram_sender.CHAT_ID
except Exception:
    pass

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
BASE_DIR = Path(__file__).resolve().parents[1]
OFFSET_FILE = BASE_DIR / "telegram_offset.txt"
