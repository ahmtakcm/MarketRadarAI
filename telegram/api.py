from __future__ import annotations

import requests

from telegram.settings import API


def tg(method, **data):
    response = requests.post(f"{API}/{method}", data=data, timeout=20)
    response.raise_for_status()
    return response.json()


def send_to_chat(chat_id: str, text: str) -> None:
    tg("sendMessage", chat_id=str(chat_id), text=str(text))
