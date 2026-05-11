from __future__ import annotations

from notifiers.telegram_notifier import send_telegram


def send_message(text: str):
    send_telegram(text)
