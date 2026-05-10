from __future__ import annotations

import logging

import requests

from config import get_telegram_credentials

logger = logging.getLogger(__name__)

MAX_TELEGRAM_TEXT = 3900


def _chunks(text: str, limit: int = MAX_TELEGRAM_TEXT):
    value = str(text or "").strip()
    if not value:
        value = "(bos mesaj)"
    for i in range(0, len(value), limit):
        yield value[i : i + limit]


def _safe_url(bot_token: str) -> str:
    return f"https://api.telegram.org/bot{bot_token}/sendMessage"


def _redact_token(value: str, bot_token: str) -> str:
    return str(value).replace(str(bot_token), "***TOKEN***")


def send_telegram(text: str, chat_id: str | None = None):
    bot_token, default_chat_id = get_telegram_credentials()
    target_chat_id = str(chat_id or default_chat_id).strip()

    if not bot_token or not target_chat_id:
        raise RuntimeError("Telegram credentials are missing")

    url = _safe_url(bot_token)
    results = []

    for chunk in _chunks(text):
        payload = {
            "chat_id": target_chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }

        response = requests.post(url, json=payload, timeout=20)

        if not response.ok:
            body = _redact_token(response.text, bot_token)
            logger.error(
                "Telegram send failed | status=%s | chat_id=%s | body=%s | text_len=%s",
                response.status_code,
                target_chat_id,
                body[:1000],
                len(chunk),
            )
            response.raise_for_status()

        results.append(response.json())

    return results[-1] if results else {"ok": False}
