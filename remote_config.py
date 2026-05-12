from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict

BASE_DIR = Path(__file__).resolve().parent
LEGACY_CONFIG_PATH = BASE_DIR / "remote_config.json"
CONFIG_PATH = Path(os.getenv("MARKETRADAR_RUNTIME_CONFIG", BASE_DIR / "runtime" / "remote_config.json"))
SCHEMA_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.05
_PROCESS_LOCK = threading.RLock()

DEFAULT_CONFIG: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "bot_active": True,
    "kill_switch": False,
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


def get_config_path() -> Path:
    return CONFIG_PATH


def get_config_lock_path() -> Path:
    return CONFIG_PATH.with_suffix(".lock")


def migrate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    migrated = merge_defaults(DEFAULT_CONFIG, config)
    migrated["schema_version"] = SCHEMA_VERSION
    return migrated


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _broken_path(path: Path) -> Path:
    return path.with_name(path.name + ".broken")


def _archive_broken(path: Path) -> None:
    broken = _broken_path(path)
    try:
        path.replace(broken)
    except PermissionError:
        broken.write_bytes(path.read_bytes())


def _replace_file(tmp: Path, target: Path) -> None:
    try:
        os.replace(tmp, target)
    except PermissionError:
        try:
            os.rename(tmp, target)
        except PermissionError:
            target.write_bytes(tmp.read_bytes())
            try:
                tmp.unlink(missing_ok=True)
            except PermissionError:
                pass


@contextmanager
def _file_lock(path: Path, timeout_seconds: float = LOCK_TIMEOUT_SECONDS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with _PROCESS_LOCK:
        with path.open("a+b") as lock_file:
            deadline = time.monotonic() + timeout_seconds
            acquired = False
            while not acquired:
                try:
                    if os.name == "nt":
                        import msvcrt

                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Runtime config lock timeout: {path}")
                    time.sleep(LOCK_POLL_SECONDS)

            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _load_config_unlocked() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        if LEGACY_CONFIG_PATH.exists():
            try:
                legacy = migrate_config(_read_json(LEGACY_CONFIG_PATH))
                _save_config_unlocked(legacy)
                return legacy
            except Exception:
                pass

        default = migrate_config({})
        _save_config_unlocked(default)
        return default

    try:
        data = _read_json(CONFIG_PATH)
    except Exception:
        try:
            _archive_broken(CONFIG_PATH)
        except Exception:
            pass
        default = migrate_config({})
        _save_config_unlocked(default)
        return default

    migrated = migrate_config(data)
    if migrated != data:
        _save_config_unlocked(migrated)
    return migrated


def load_config() -> Dict[str, Any]:
    with _file_lock(get_config_lock_path()):
        return _load_config_unlocked()


def _save_config_unlocked(config: Dict[str, Any]) -> Dict[str, Any]:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = migrate_config(config)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    _replace_file(tmp, CONFIG_PATH)
    return payload


def save_config(config: Dict[str, Any]) -> None:
    with _file_lock(get_config_lock_path()):
        _save_config_unlocked(config)


def update_config(mutator: Callable[[Dict[str, Any]], Any]) -> Dict[str, Any]:
    with _file_lock(get_config_lock_path()):
        cfg = _load_config_unlocked()
        mutator(cfg)
        return _save_config_unlocked(cfg)


def get_active_modes(config: Dict[str, Any]) -> list[str]:
    mode_only = config.get("mode_only")
    if mode_only and mode_only != "off":
        return [mode_only]
    return [k for k, v in config.get("modes", {}).items() if v]


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").upper().strip()

