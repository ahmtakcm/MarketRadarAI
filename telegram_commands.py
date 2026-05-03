from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import requests

from config import get_telegram_credentials
from core.exchange_client import validate_futures_symbol
from remote_config import load_config, save_config

BASE_DIR = Path(__file__).resolve().parent
_OFFSET_FILE = BASE_DIR / "telegram_offset.txt"
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


def _allowed_chat_id() -> str:
    _, chat_id = get_telegram_credentials()
    return str(chat_id).strip()


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


def _tg(method: str, **data):
    response = requests.post(f"{_api_base()}/{method}", data=data, timeout=20)
    response.raise_for_status()
    return response.json()


def _safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        symbol = str(value or "").upper().strip()
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def _watchlist_status_text(cfg):
    symbols = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    if not symbols:
        return "Watchlist bos."

    lines = ["WATCHLIST", ""]
    for symbol in symbols:
        ok, reason = validate_futures_symbol(symbol)
        status = "valid" if ok else f"invalid: {reason}"
        lines.append(f"{symbol}: {status}")

    return "\n".join(lines)


def handle_command_message(message, send_telegram):
    chat_id = str(message.get("chat", {}).get("id", ""))
    allowed_chat_id = _allowed_chat_id()

    if not allowed_chat_id or chat_id != allowed_chat_id:
        logging.warning("Yetkisiz Telegram mesaji reddedildi: chat_id=%s", chat_id)
        return

    text = str(message.get("text", "")).strip()
    if not text.startswith("/"):
        return

    cfg = load_config()
    cmd = text.split()[0].lower()

    if cmd in {"/ping", "/start"}:
        send_telegram("pong")
        return

    if cmd == "/status":
        active = "aktif" if cfg.get("bot_active", True) else "pasif"
        kill_switch = "acik" if cfg.get("kill_switch", False) else "kapali"
        watchlist = cfg.get("watchlist", {}).get("symbols", [])
        send_telegram(
            "BOT DURUMU\n\n"
            f"Bot: {active}\n"
            f"Kill switch: {kill_switch}\n"
            f"Watchlist: {', '.join(watchlist) or 'bos'}"
        )
        return

    if cmd in {"/symbols", "/watchlist"}:
        send_telegram(_watchlist_status_text(cfg))
        return

    if cmd in {"/addsymbol", "/add_symbol"}:
        parts = text.split()
        if len(parts) < 2:
            send_telegram("Kullanim: /addsymbol BTCUSDT")
            return

        symbol = str(parts[1]).upper().strip()
        ok, reason = validate_futures_symbol(symbol)
        if not ok:
            send_telegram(f"Sembol eklenmedi: {symbol}\nNeden: {reason}")
            return

        watchlist = cfg.setdefault("watchlist", {}).setdefault("symbols", [])
        existing = _safe_symbols(watchlist)
        if symbol in existing:
            send_telegram(f"Sembol zaten watchlist icinde: {symbol}")
            return

        existing.append(symbol)
        cfg["watchlist"]["symbols"] = existing
        cfg["watchlist"]["watched_symbols"] = existing
        save_config(cfg)
        send_telegram(f"Sembol watchlist'e eklendi: {symbol}")
        return

    if cmd == "/scan_now":
        cfg.setdefault("runtime", {})["force_scan_once"] = True
        save_config(cfg)
        send_telegram("Manuel tarama istegi alindi.")
        return

    send_telegram("Komut sistemi su an kisitli modda. Desteklenen komutlar: /status /watchlist /addsymbol /scan_now /ping")


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
