import requests

from config import BOT_TOKEN, CHAT_ID


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
