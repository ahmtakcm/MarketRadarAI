import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"

with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    SETTINGS = json.load(f)


BOT_TOKEN = SETTINGS["telegram"]["bot_token"]
CHAT_ID = SETTINGS["telegram"]["chat_id"]

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
# Tarama süresi artık sabit interval ile değil,
# core/scheduler.py içindeki mum kapanış zamanlamasıyla belirlenir.
MODE_TIMEFRAMES = {
    "scalp": {
        "label": "Scalping",
        "bias": "15m",
        "setup": "5m",
        "entry": "3m",
    },
    "intraday": {
        "label": "Gün İçi",
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
