import json
import time
from pathlib import Path

MAX_SIGNAL_AGE_SECONDS = 6 * 60 * 60  # 6 saat

def get_macro_signal():
    path = Path.home() / "RiskRadarAI/storage/macro_trade_signals.json"

    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = int(data.get("timestamp") or 0)

        if ts and time.time() - ts > MAX_SIGNAL_AGE_SECONDS:
            return {}

        return data
    except Exception:
        return {}

def macro_direction_for_symbol(symbol: str):
    data = get_macro_signal()
    impact = data.get("impact") or {}
    symbol = (symbol or "").upper()

    if symbol.startswith("BTC"):
        return impact.get("btc")
    if symbol.startswith("XAU"):
        return impact.get("gold")
    if symbol.startswith("XAG"):
        return impact.get("silver")

    return None
