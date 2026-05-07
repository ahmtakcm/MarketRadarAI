from __future__ import annotations

import datetime as dt
from pathlib import Path

from config import APP_LOG_PATH
from remote_config import get_active_modes
from telegram.router import SUPPORTED_COMMANDS

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BASE_DIR / "storage"
BOTFATHER_COMMANDS_PATH = BASE_DIR / "BOTFATHER_COMMANDS.txt"


def _safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        symbol = str(value or "").upper().strip()
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def _utc_now_text():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _file_status_text(path):
    file_path = Path(path)
    if not file_path.exists():
        return "missing"

    try:
        stat = file_path.stat()
        modified_at = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
        modified_text = modified_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"{modified_text} | {stat.st_size} bytes"
    except Exception as exc:
        return f"unreadable: {exc}"


def help_text():
    lines = ["DESTEKLENEN KOMUTLAR", ""]
    for command, description in SUPPORTED_COMMANDS.items():
        if command == "/start":
            continue
        lines.append(f"{command} - {description}")
    lines.append("")
    lines.append("ADMIN komutlari gruptan yazilabilir; sonuc yetkili adminin ozel sohbetine gider.")
    return "\n".join(lines)


def status_text(cfg):
    active = "aktif" if cfg.get("bot_active", True) else "pasif"
    kill_switch = "acik" if cfg.get("kill_switch", False) else "kapali"
    quiet = "acik" if cfg.get("notifications", {}).get("quiet_mode", False) else "kapali"
    explain = "acik" if cfg.get("explain_signals", True) else "kapali"
    watchlist = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    modes = get_active_modes(cfg)
    return (
        "BOT DURUMU\n\n"
        f"Bot: {active}\n"
        f"Kill switch: {kill_switch}\n"
        f"Quiet mode: {quiet}\n"
        f"Explain signals: {explain}\n"
        f"Aktif modlar: {', '.join(modes) or 'yok'}\n"
        f"Watchlist: {', '.join(watchlist) or 'bos'}"
    )


def health_text(cfg, polling_enabled: bool):
    watchlist = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    return (
        "HEALTH\n\n"
        f"Zaman: {_utc_now_text()}\n"
        f"Command polling: {'enabled' if polling_enabled else 'disabled'}\n"
        f"Bot active: {cfg.get('bot_active', True)}\n"
        f"Kill switch: {cfg.get('kill_switch', False)}\n"
        f"Watchlist count: {len(watchlist)}\n"
        f"Watchlist: {', '.join(watchlist) or 'bos'}\n"
        f"App log: {_file_status_text(APP_LOG_PATH)}\n"
        f"Telegram err: {_file_status_text(STORAGE_DIR / 'telegram_commands.err')}\n"
        f"MEXC err: {_file_status_text(STORAGE_DIR / 'mexc.err')}\n"
        f"Remote config: ok"
    )


def modes_text(cfg):
    modes = cfg.get("modes", {})
    active = get_active_modes(cfg)
    lines = ["MODLAR", ""]
    for mode in ["scalp", "intraday", "midterm"]:
        lines.append(f"{mode}: {'acik' if modes.get(mode) else 'kapali'}")
    lines.append("")
    lines.append(f"mode_only: {cfg.get('mode_only') or 'off'}")
    lines.append(f"aktif: {', '.join(active) or 'yok'}")
    return "\n".join(lines)


def filters_text(cfg):
    filters = cfg.get("filters", {})
    lines = ["FILTRELER", ""]
    for key in sorted(filters):
        lines.append(f"{key}: {filters.get(key)}")
    return "\n".join(lines)


def _tail_file(path: Path, lines: int = 25) -> list[str]:
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return content[-lines:]
    except Exception as exc:
        return [f"Log okunamadi: {exc}"]


def log_text():
    rows = _tail_file(APP_LOG_PATH, lines=25)
    if not rows:
        return "LOG\n\nLog kaydi yok."
    return "LOG\n\n" + "\n".join(rows)[-3500:]


def error_log_text():
    rows = []
    for path in [APP_LOG_PATH, STORAGE_DIR / "telegram_commands.err", STORAGE_DIR / "mexc.err"]:
        for line in _tail_file(path, lines=120):
            upper = line.upper()
            if "ERROR" in upper or "WARNING" in upper or "TRACEBACK" in upper or "EXCEPTION" in upper:
                rows.append(f"{path.name}: {line}")
    if not rows:
        return "ERROR LOG\n\nSon hata/uyari kaydi yok."
    return "ERROR LOG\n\n" + "\n".join(rows[-25:])[-3500:]


def botfather_commands_text():
    if BOTFATHER_COMMANDS_PATH.exists():
        return BOTFATHER_COMMANDS_PATH.read_text(encoding="utf-8", errors="ignore")[-3500:]
    return "\n".join(f"{cmd[1:]} - {desc}" for cmd, desc in SUPPORTED_COMMANDS.items() if cmd != "/start")
