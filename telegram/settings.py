from __future__ import annotations

import os
from pathlib import Path

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

ADMIN_CHAT_ID = "1218508355"
GROUP_CHAT_ID = "-1003949299046"

# Backward compatibility for older single-chat deployments.
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()

if not ALLOWED_CHAT_ID:
    try:
        from config import CHAT_ID as CONFIG_CHAT_ID

        ALLOWED_CHAT_ID = str(CONFIG_CHAT_ID).strip()
    except Exception:
        pass

if not GROUP_CHAT_ID and ALLOWED_CHAT_ID:
    GROUP_CHAT_ID = ALLOWED_CHAT_ID

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
