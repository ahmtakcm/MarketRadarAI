import requests

from config import get_telegram_credentials


def send_telegram(text: str):
    bot_token, chat_id = get_telegram_credentials()
    if not bot_token or not chat_id:
        raise RuntimeError("Telegram credentials are missing")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": str(text),
    }
    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()
