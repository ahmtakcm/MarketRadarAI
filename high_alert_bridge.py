import json
from pathlib import Path

STATE_PATH = Path.home() / "RiskRadarAI/storage/macro_high_alert_state.json"

def get_high_alert():
    if not STATE_PATH.exists():
        return {}

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))

        if not data.get("active"):
            return {}

        until = data.get("until")
        if until:
            # basit zaman kontrolü
            from datetime import datetime, timezone
            until_dt = datetime.fromisoformat(until)
            if datetime.now(timezone.utc) > until_dt:
                return {}

        return data
    except Exception:
        return {}

def is_high_alert():
    return bool(get_high_alert())

def get_high_alert_assets():
    data = get_high_alert()
    return data.get("assets") or []

