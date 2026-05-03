import requests

from config import get_telegram_credentials


def send_telegram(text: str, chat_id: str | None = None):
    bot_token, default_chat_id = get_telegram_credentials()
    target_chat_id = str(chat_id or default_chat_id).strip()
    if not bot_token or not target_chat_id:
        raise RuntimeError("Telegram credentials are missing")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": str(text),
    }
    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()
