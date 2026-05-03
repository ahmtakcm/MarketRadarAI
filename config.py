import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"

with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    SETTINGS = json.load(f)


def get_telegram_credentials():
    telegram = SETTINGS.get("telegram", {})
    token = os.getenv("TELEGRAM_BOT_TOKEN") or telegram.get("bot_token", "")
    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("TELEGRAM_ALLOWED_CHAT_ID")
        or telegram.get("chat_id", "")
    )
    return str(token).strip(), str(chat_id).strip()


BOT_TOKEN, CHAT_ID = get_telegram_credentials()

REQUESTED_SYMBOLS = SETTINGS["symbols"]

TIMEFRAMES = {
    "scalp": "3m",
    "intraday": "15m",
    "midterm": "1h",
}

COMMENTARY_SYMBOLS = set(SETTINGS["commentary_symbols"])

SIGNAL_HORIZONS_BARS = SETTINGS.get("signal_horizons_bars", [1, 3, 5])

ENABLED_STRATEGIES = SETTINGS.get("enabled_strategies", ["fibb_bands"])
STRATEGY_SETTINGS = SETTINGS.get("strategy_settings", {})

BINANCE_FAPI_BASE = "https://fapi.binance.com"
BINANCE_WS_BASE = "wss://fstream.binance.com/stream?streams="

APP_LOG_PATH = BASE_DIR / "logs" / "app.log"
STATE_FILE_PATH = BASE_DIR / "data" / "state.json"
SIGNALS_LOG_PATH = BASE_DIR / "data" / "signals_log.jsonl"
PERFORMANCE_LOG_PATH = BASE_DIR / "data" / "performance_log.jsonl"


# Mode-based timeframe architecture
# Tarama suresi artik sabit interval ile degil,
# core/scheduler.py icindeki mum kapanis zamanlamasiyla belirlenir.
MODE_TIMEFRAMES = {
    "scalp": {
        "label": "Scalping",
        "bias": "15m",
        "setup": "5m",
        "entry": "3m",
    },
    "intraday": {
        "label": "Gun Ici",
        "bias": "4h",
        "setup": "1h",
        "entry": "15m",
    },
    "midterm": {
        "label": "Orta Vade",
        "bias": "1d",
        "setup": "4h",
        "entry": "1h",
    },
}
