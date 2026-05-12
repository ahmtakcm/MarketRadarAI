from __future__ import annotations

import logging
import threading

from telegram.settings import OFFSET_FILE

telegram_poll_lock = threading.Lock()


def load_last_update_id() -> int:
    try:
        if OFFSET_FILE.exists():
            raw = OFFSET_FILE.read_text(encoding="utf-8").strip()
            if raw:
                return int(raw)
    except Exception:
        try:
            logging.warning("Telegram offset okunamadi")
        except Exception:
            pass
    return 0


def save_last_update_id(update_id: int) -> None:
    try:
        OFFSET_FILE.write_text(str(int(update_id)), encoding="utf-8")
    except Exception:
        try:
            logging.exception("Telegram offset dosyasi yazilamadi")
        except Exception:
            pass
