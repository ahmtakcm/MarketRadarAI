from __future__ import annotations

import datetime as dt
import logging
import os
import threading
from pathlib import Path

import requests

from config import APP_LOG_PATH, get_telegram_admin_chat_ids, get_telegram_credentials
from core.exchange_client import validate_futures_symbol
from remote_config import get_active_modes, load_config, save_config
from signal_journal import build_explain_last_text, build_performance_today_text, get_last_signal
from telegram.router import (
    ADD_SYMBOL_COMMANDS,
    PRIVATE_ADMIN_COMMANDS,
    REMOVE_SYMBOL_COMMANDS,
    SUPPORTED_COMMANDS,
    WATCHLIST_COMMANDS,
    command_args,
    command_name,
)

BASE_DIR = Path(__file__).resolve().parent
_OFFSET_FILE = BASE_DIR / "telegram_offset.txt"
_STORAGE_DIR = BASE_DIR / "storage"
_BOTFATHER_COMMANDS_PATH = BASE_DIR / "BOTFATHER_COMMANDS.txt"
_telegram_poll_lock = threading.Lock()
_last_update_id = 0

def telegram_polling_enabled() -> bool:
    env_value = os.getenv("TELEGRAM_COMMANDS_ENABLED", "").strip().lower()
    if env_value in {"1", "true", "yes", "on"}:
        return True

    try:
        cfg = load_config()
    except Exception:
        return False

    telegram_cfg = cfg.get("telegram", {})
    return bool(telegram_cfg.get("commands_enabled") and telegram_cfg.get("polling_enabled"))


def _api_base() -> str:
    bot_token, _ = get_telegram_credentials()
    if not bot_token:
        raise RuntimeError("Telegram bot token is missing")
    return f"https://api.telegram.org/bot{bot_token}"


def _split_chat_ids(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = str(value).replace(";", ",").replace("\n", ",").split(",")

    result = []
    seen = set()
    for item in raw_items:
        chat_id = str(item or "").strip()
        if chat_id and chat_id not in seen:
            result.append(chat_id)
            seen.add(chat_id)
    return result


def _dedupe_ids(values):
    result = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _allowed_chat_ids(cfg):
    telegram_cfg = cfg.get("telegram", {})
    ids = []
    ids.extend(get_telegram_admin_chat_ids())
    ids.extend(_split_chat_ids(telegram_cfg.get("admin_chat_ids")))
    ids.extend(_split_chat_ids(telegram_cfg.get("allowed_chat_ids")))
    ids.extend(_split_chat_ids(telegram_cfg.get("admin_chat_id")))
    ids.extend(_split_chat_ids(telegram_cfg.get("notification_chat_id")))
    return _dedupe_ids(ids)


def _admin_user_ids(cfg):
    telegram_cfg = cfg.get("telegram", {})
    ids = []
    ids.extend(_split_chat_ids(telegram_cfg.get("admin_user_ids")))
    ids.extend(get_telegram_admin_chat_ids())
    ids.extend(_split_chat_ids(telegram_cfg.get("admin_chat_ids")))
    ids.extend(_split_chat_ids(telegram_cfg.get("allowed_chat_ids")))
    ids.extend(_split_chat_ids(telegram_cfg.get("admin_chat_id")))
    return [item for item in _dedupe_ids(ids) if not item.startswith("-")]


def _sender_id(message) -> str:
    return str(message.get("from", {}).get("id", "")).strip()


def _is_private_chat(chat_id: str) -> bool:
    return bool(str(chat_id or "").strip()) and not str(chat_id).startswith("-")


def _load_last_update_id() -> int:
    try:
        if _OFFSET_FILE.exists():
            raw = _OFFSET_FILE.read_text(encoding="utf-8").strip()
            if raw:
                return int(raw)
    except Exception:
        logging.warning("Telegram offset okunamadi")
    return 0


def _save_last_update_id(update_id: int) -> None:
    try:
        _OFFSET_FILE.write_text(str(int(update_id)), encoding="utf-8")
    except Exception:
        logging.exception("Telegram offset dosyasi yazilamadi")


def _safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        symbol = str(value or "").upper().strip()
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def _send_text(send_telegram, chat_id: str, text: str):
    body = str(text or "")
    if not body.strip():
        body = "-"

    max_len = 3900
    chunks = [body[i:i + max_len] for i in range(0, len(body), max_len)] or [body]
    for chunk in chunks:
        send_telegram(chunk, chat_id=chat_id)


def _send_private_admin_result(send_telegram, command_chat_id: str, admin_user_id: str, text: str):
    try:
        _send_text(send_telegram, admin_user_id, text)
        return
    except Exception as exc:
        logging.exception("Admin cevabi ozel sohbete gonderilemedi: %s", exc)

    if command_chat_id != admin_user_id:
        _send_text(
            send_telegram,
            command_chat_id,
            "Admin islemi uygulandi; ancak ozel cevap gonderilemedi. Botla ozelden /start yazip tekrar dene.",
        )
    else:
        raise RuntimeError("Admin cevabi gonderilemedi")


def _watchlist_status_text(cfg):
    symbols = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    if not symbols:
        return "WATCHLIST\n\nWatchlist bos."

    lines = ["WATCHLIST", ""]
    for symbol in symbols:
        ok, reason = validate_futures_symbol(symbol)
        status = "valid" if ok else f"invalid: {reason}"
        lines.append(f"{symbol}: {status}")

    return "\n".join(lines)


def _help_text():
    lines = ["DESTEKLENEN KOMUTLAR", ""]
    for command, description in SUPPORTED_COMMANDS.items():
        if command == "/start":
            continue
        lines.append(f"{command} - {description}")
    lines.append("")
    lines.append("ADMIN komutlari gruptan yazilabilir; sonuc yetkili adminin ozel sohbetine gider.")
    return "\n".join(lines)


def _status_text(cfg):
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


def _health_text(cfg):
    return (
        "HEALTH\n\n"
        f"Zaman: {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Command polling: {'enabled' if telegram_polling_enabled() else 'disabled'}\n"
        f"Bot active: {cfg.get('bot_active', True)}\n"
        f"Kill switch: {cfg.get('kill_switch', False)}\n"
        f"Watchlist count: {len(_safe_symbols(cfg.get('watchlist', {}).get('symbols', [])))}\n"
        f"Remote config: ok"
    )


def _modes_text(cfg):
    modes = cfg.get("modes", {})
    active = get_active_modes(cfg)
    lines = ["MODLAR", ""]
    for mode in ["scalp", "intraday", "midterm"]:
        lines.append(f"{mode}: {'acik' if modes.get(mode) else 'kapali'}")
    lines.append("")
    lines.append(f"mode_only: {cfg.get('mode_only') or 'off'}")
    lines.append(f"aktif: {', '.join(active) or 'yok'}")
    return "\n".join(lines)


def _filters_text(cfg):
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


def _log_text():
    rows = _tail_file(APP_LOG_PATH, lines=25)
    if not rows:
        return "LOG\n\nLog kaydi yok."
    return "LOG\n\n" + "\n".join(rows)[-3500:]


def _error_log_text():
    rows = []
    for path in [APP_LOG_PATH, _STORAGE_DIR / "telegram_commands.err", _STORAGE_DIR / "mexc.err"]:
        for line in _tail_file(path, lines=120):
            upper = line.upper()
            if "ERROR" in upper or "WARNING" in upper or "TRACEBACK" in upper or "EXCEPTION" in upper:
                rows.append(f"{path.name}: {line}")
    if not rows:
        return "ERROR LOG\n\nSon hata/uyari kaydi yok."
    return "ERROR LOG\n\n" + "\n".join(rows[-25:])[-3500:]


def _botfather_commands_text():
    if _BOTFATHER_COMMANDS_PATH.exists():
        return _BOTFATHER_COMMANDS_PATH.read_text(encoding="utf-8", errors="ignore")[-3500:]
    return "\n".join(f"{cmd[1:]} - {desc}" for cmd, desc in SUPPORTED_COMMANDS.items() if cmd != "/start")


def _add_symbol(cfg, symbol: str) -> str:
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        return "Kullanim: /addsymbol BTCUSDT"

    ok, reason = validate_futures_symbol(symbol)
    if not ok:
        return f"Sembol eklenmedi: {symbol}\nNeden: {reason}"

    watchlist = cfg.setdefault("watchlist", {}).setdefault("symbols", [])
    existing = _safe_symbols(watchlist)
    if symbol in existing:
        return f"Sembol zaten watchlist icinde: {symbol}"

    existing.append(symbol)
    cfg["watchlist"]["symbols"] = existing
    cfg["watchlist"]["watched_symbols"] = existing
    save_config(cfg)
    return f"Sembol watchlist'e eklendi: {symbol}"


def _remove_symbol(cfg, symbol: str) -> str:
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        return "Kullanim: /removesymbol BTCUSDT"

    existing = _safe_symbols(cfg.setdefault("watchlist", {}).setdefault("symbols", []))
    if symbol not in existing:
        return f"Sembol watchlist icinde yok: {symbol}"

    updated = [item for item in existing if item != symbol]
    cfg["watchlist"]["symbols"] = updated
    cfg["watchlist"]["watched_symbols"] = updated
    save_config(cfg)
    return f"Sembol watchlist'ten silindi: {symbol}"


def _set_bot_active(cfg, enabled: bool) -> str:
    cfg["bot_active"] = bool(enabled)
    save_config(cfg)
    return f"Bot {'aktif' if enabled else 'pasif'} moda alindi."


def _set_quiet_mode(cfg, enabled: bool) -> str:
    cfg.setdefault("notifications", {})["quiet_mode"] = bool(enabled)
    save_config(cfg)
    return f"Quiet mode {'acildi' if enabled else 'kapatildi'}."


def _set_kill_switch(cfg, enabled: bool) -> str:
    cfg["kill_switch"] = bool(enabled)
    save_config(cfg)
    return f"Kill switch {'acildi' if enabled else 'kapatildi'}."


def _set_mode(cfg, mode: str, enabled: bool) -> str:
    cfg.setdefault("modes", {})[mode] = bool(enabled)
    save_config(cfg)
    return f"{mode} modu {'acildi' if enabled else 'kapatildi'}.\n\n" + _modes_text(cfg)


def _set_mode_only(cfg, args: list[str]) -> str:
    if not args:
        return "Kullanim: /mode_only off|scalp|intraday|midterm"

    value = str(args[0]).lower().strip()
    if value not in {"off", "scalp", "intraday", "midterm"}:
        return "Gecersiz mode_only. Kullanim: /mode_only off|scalp|intraday|midterm"

    cfg["mode_only"] = None if value == "off" else value
    save_config(cfg)
    return "Mode-only guncellendi.\n\n" + _modes_text(cfg)


def _set_filter(cfg, key: str, enabled: bool) -> str:
    cfg.setdefault("filters", {})[key] = bool(enabled)
    save_config(cfg)
    return f"{key} {'acildi' if enabled else 'kapatildi'}.\n\n" + _filters_text(cfg)


def _set_explain_signals(cfg, enabled: bool) -> str:
    cfg["explain_signals"] = bool(enabled)
    save_config(cfg)
    return f"Sinyal aciklamalari {'acildi' if enabled else 'kapatildi'}."


def _handle_private_admin_command(cmd: str, args: list[str], cfg) -> str:
    if cmd == "/start_bot":
        return _set_bot_active(cfg, True)
    if cmd == "/stop_bot":
        return _set_bot_active(cfg, False)
    if cmd == "/quiet_on":
        return _set_quiet_mode(cfg, True)
    if cmd == "/quiet_off":
        return _set_quiet_mode(cfg, False)
    if cmd == "/kill_switch_on":
        return _set_kill_switch(cfg, True)
    if cmd == "/kill_switch_off":
        return _set_kill_switch(cfg, False)
    if cmd == "/scalp_on":
        return _set_mode(cfg, "scalp", True)
    if cmd == "/scalp_off":
        return _set_mode(cfg, "scalp", False)
    if cmd == "/intraday_on":
        return _set_mode(cfg, "intraday", True)
    if cmd == "/intraday_off":
        return _set_mode(cfg, "intraday", False)
    if cmd == "/midterm_on":
        return _set_mode(cfg, "midterm", True)
    if cmd == "/midterm_off":
        return _set_mode(cfg, "midterm", False)
    if cmd == "/mode_only":
        return _set_mode_only(cfg, args)
    if cmd == "/fake_filter_on":
        return _set_filter(cfg, "fake_breakout_filter", True)
    if cmd == "/fake_filter_off":
        return _set_filter(cfg, "fake_breakout_filter", False)
    if cmd == "/volume_filter_on":
        return _set_filter(cfg, "volume_confirmation", True)
    if cmd == "/volume_filter_off":
        return _set_filter(cfg, "volume_confirmation", False)
    if cmd == "/explain_on":
        return _set_explain_signals(cfg, True)
    if cmd == "/explain_off":
        return _set_explain_signals(cfg, False)
    return "Desteklenmeyen admin komutu."


def handle_command_message(message, send_telegram):
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = str(message.get("text", "")).strip()
    if not text.startswith("/"):
        return

    cfg = load_config()
    allowed_chat_ids = _allowed_chat_ids(cfg)
    if chat_id not in allowed_chat_ids:
        logging.warning("Yetkisiz Telegram mesaji reddedildi: chat_id=%s", chat_id)
        return

    cmd = command_name(text)
    args = command_args(text)
    sender_id = _sender_id(message)

    if cmd in PRIVATE_ADMIN_COMMANDS:
        if _is_private_chat(chat_id):
            _send_text(send_telegram, chat_id, _handle_private_admin_command(cmd, args, cfg))
            return

        if sender_id not in _admin_user_ids(cfg):
            logging.warning("Yetkisiz grup admin komutu reddedildi: chat_id=%s sender_id=%s cmd=%s", chat_id, sender_id, cmd)
            _send_text(send_telegram, chat_id, "Bu admin komutu icin yetkin yok.")
            return

        result = _handle_private_admin_command(cmd, args, cfg)
        _send_private_admin_result(send_telegram, chat_id, sender_id, result)
        return

    if cmd in {"/ping", "/start"}:
        _send_text(send_telegram, chat_id, "pong" if cmd == "/ping" else _help_text())
        return

    if cmd == "/help":
        _send_text(send_telegram, chat_id, _help_text())
        return

    if cmd == "/status":
        _send_text(send_telegram, chat_id, _status_text(cfg))
        return

    if cmd == "/health":
        _send_text(send_telegram, chat_id, _health_text(cfg))
        return

    if cmd in WATCHLIST_COMMANDS:
        _send_text(send_telegram, chat_id, _watchlist_status_text(cfg))
        return

    if cmd in ADD_SYMBOL_COMMANDS:
        _send_text(send_telegram, chat_id, _add_symbol(cfg, args[0] if args else ""))
        return

    if cmd in REMOVE_SYMBOL_COMMANDS:
        _send_text(send_telegram, chat_id, _remove_symbol(cfg, args[0] if args else ""))
        return

    if cmd == "/scan_now":
        cfg.setdefault("runtime", {})["force_scan_once"] = True
        save_config(cfg)
        _send_text(send_telegram, chat_id, "Manuel tarama istegi alindi.")
        return

    if cmd == "/last_signal":
        _send_text(send_telegram, chat_id, get_last_signal())
        return

    if cmd == "/explain_last":
        _send_text(send_telegram, chat_id, build_explain_last_text())
        return

    if cmd == "/performance_today":
        _send_text(send_telegram, chat_id, build_performance_today_text())
        return

    if cmd == "/modes":
        _send_text(send_telegram, chat_id, _modes_text(cfg))
        return

    if cmd == "/filters":
        _send_text(send_telegram, chat_id, _filters_text(cfg))
        return

    if cmd == "/log":
        _send_text(send_telegram, chat_id, _log_text())
        return

    if cmd == "/error_log":
        _send_text(send_telegram, chat_id, _error_log_text())
        return

    if cmd == "/botfather_commands":
        _send_text(send_telegram, chat_id, _botfather_commands_text())
        return

    _send_text(send_telegram, chat_id, "Desteklenmeyen komut. /help yazabilirsin.")


def poll_telegram_commands(send_telegram):
    global _last_update_id

    if not telegram_polling_enabled():
        return

    if not _telegram_poll_lock.acquire(blocking=False):
        return

    try:
        if not _last_update_id:
            _last_update_id = _load_last_update_id()

        params = {
            "timeout": 0,
            "allowed_updates": ["message"],
        }
        if _last_update_id:
            params["offset"] = _last_update_id + 1

        response = requests.get(f"{_api_base()}/getUpdates", params=params, timeout=6)
        data = response.json()

        if not data.get("ok"):
            logging.warning("Telegram getUpdates ok=false: %s", data)
            return

        for update in data.get("result", []):
            update_id = update.get("update_id")
            if update_id is not None:
                _last_update_id = int(update_id)
                _save_last_update_id(_last_update_id)

            message = update.get("message") or update.get("edited_message")
            if message:
                handle_command_message(message, send_telegram)
    except Exception as exc:
        logging.exception("Telegram komut kontrol hatasi: %s", exc)
    finally:
        try:
            _telegram_poll_lock.release()
        except RuntimeError:
            pass
