from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "remote_config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "explain_signals": True,
    "modes": {
        "scalp": False,
        "intraday": True,
        "midterm": True,
    },
    "mode_only": None,
    "risk_level": "normal",
    "filters": {
        "fake_breakout_filter": True,
        "volume_confirmation": True,
        "min_volume": None,
        "fake_sensitivity": "medium",
        "min_trend_strength": "medium",
    },
    "limits": {
        "cooldown_minutes": 30,
        "symbol_cooldown_minutes": {},
        "max_signals_per_day": 20,
        "max_same_symbol_per_day": 3,
    },
    "watchlist": {
        "symbols": [],
        "watched_symbols": [],
    },
    "notifications": {
        "notify_only": "all",
    },
    "update": {
        "pending_zip": None,
        "last_status": "idle",
    },
    "runtime": {
        "last_restart_request": None,
        "last_update_apply": None,
        "force_scan_once": False
    },
}


def merge_defaults(default: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(default)
    for key, value in current.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_defaults(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        # utf-8-sig: PowerShell/Notepad BOM sorununu gÃ¼venli Ã§Ã¶zer.
        with CONFIG_PATH.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        broken = CONFIG_PATH.with_suffix(".broken.json")
        try:
            CONFIG_PATH.replace(broken)
        except Exception:
            pass
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    return merge_defaults(DEFAULT_CONFIG, data)


def save_config(config: Dict[str, Any]) -> None:
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)


def get_active_modes(config: Dict[str, Any]) -> list[str]:
    mode_only = config.get("mode_only")
    if mode_only and mode_only != "off":
        return [mode_only]
    return [k for k, v in config.get("modes", {}).items() if v]


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").upper().strip()

