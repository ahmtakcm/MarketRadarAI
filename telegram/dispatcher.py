from __future__ import annotations

import logging

import requests

from telegram.handlers import handle_command_message
from telegram.offsets import load_last_update_id, save_last_update_id, telegram_poll_lock
from telegram.settings import API

last_update_id = load_last_update_id()


def poll_telegram_commands(send_telegram):
    # Non-overlapping getUpdates with persistent offset.
    global last_update_id
    if not telegram_poll_lock.acquire(blocking=False):
        return
    try:
        params = {
            "timeout": 0,
            "allowed_updates": ["message"],
        }
        if last_update_id:
            params["offset"] = last_update_id + 1

        response = requests.get(f"{API}/getUpdates", params=params, timeout=6)
        try:
            data = response.json()
        except Exception:
            logging.exception("Telegram getUpdates JSON parse hatasi")
            return

        if not data.get("ok"):
            logging.warning("Telegram getUpdates ok=false: %s", data)
            return

        for update in data.get("result", []):
            update_id = update.get("update_id")
            if update_id is not None:
                last_update_id = int(update_id)
                save_last_update_id(last_update_id)

            message = update.get("message") or update.get("edited_message")
            if message:
                text = str(message.get("text") or "").strip()
                if text:
                    logging.info("Telegram command received: %s", text.split()[0])
                handle_command_message(message, send_telegram)
    except Exception as e:
        logging.exception("Telegram komut kontrol hatasi: %s", e)
    finally:
        try:
            telegram_poll_lock.release()
        except RuntimeError:
            pass
