from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

import requests

from core.exchange_client import get_valid_futures_symbols
from health_monitor import build_health_text
from remote_config import get_active_modes, load_config, normalize_symbol, save_config
from signal_journal import build_performance_today_text

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

ADMIN_CHAT_ID = "1218508355"
GROUP_CHAT_ID = "-1003949299046"

# backward compatibility
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()

# config fallback (env yoksa settings.json kullan)
if not ALLOWED_CHAT_ID:
    try:
        from config import CHAT_ID as CONFIG_CHAT_ID
        ALLOWED_CHAT_ID = str(CONFIG_CHAT_ID).strip()
    except Exception:
        pass

# fallback compatibility
if not GROUP_CHAT_ID and ALLOWED_CHAT_ID:
    GROUP_CHAT_ID = ALLOWED_CHAT_ID

ADMIN_PRIVATE_COMMANDS = {
    "/help",
    "/ping",
    "/health",
    "/status",
    "/scan_now",
    "/start",
    "/stop",
    "/restart",
    "/modes",
    "/scalp_on",
    "/scalp_off",
    "/filters",
    "/fake_filter_on",
    "/fake_filter_off",
    "/volume_filter_on",
    "/volume_filter_off",
    "/watchlist",
    "/add_symbol",
    "/remove_symbol",
    "/performance_today",
    "/log",
    "/error_log",
}

# Group commands intentionally disabled for now.
GROUP_SAFE_COMMANDS = set()

BOTFATHER_COMMANDS = [
    ("help", "help"),
    ("ping", "ping"),
    ("health", "health"),
    ("status", "status"),
    ("scan_now", "scan_now"),
    ("start", "start"),
    ("stop", "stop"),
    ("restart", "restart"),
    ("modes", "modes"),
    ("scalp_on", "scalp_on"),
    ("scalp_off", "scalp_off"),
    ("filters", "filters"),
    ("fake_filter_on", "fake_filter_on"),
    ("fake_filter_off", "fake_filter_off"),
    ("volume_filter_on", "volume_filter_on"),
    ("volume_filter_off", "volume_filter_off"),
    ("watchlist", "watchlist"),
    ("add_symbol", "add_symbol"),
    ("remove_symbol", "remove_symbol"),
    ("performance_today", "performance_today"),
    ("log", "log"),
    ("error_log", "error_log"),
]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Ensure command polling uses the same Telegram credentials as message sending.
try:
    from notifiers import telegram_notifier as _telegram_sender
    if hasattr(_telegram_sender, "BOT_TOKEN"):
        BOT_TOKEN = _telegram_sender.BOT_TOKEN
    if hasattr(_telegram_sender, "CHAT_ID"):
        CHAT_ID = _telegram_sender.CHAT_ID
    API = f"https://api.telegram.org/bot{BOT_TOKEN}"
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent

# PERSISTENT_TELEGRAM_OFFSET_PATCH_V1_START
_OFFSET_FILE = Path(__file__).resolve().parent / "telegram_offset.txt"
_telegram_poll_lock = threading.Lock()


def _load_last_update_id() -> int:
    try:
        if _OFFSET_FILE.exists():
            raw = _OFFSET_FILE.read_text(encoding="utf-8").strip()
            if raw:
                return int(raw)
    except Exception:
        try:
            logging.warning("Telegram offset okunamadı")
        except Exception:
            pass
    return 0


def _save_last_update_id(update_id: int) -> None:
    try:
        _OFFSET_FILE.write_text(str(int(update_id)), encoding="utf-8")
    except Exception:
        try:
            logging.exception("Telegram offset dosyası yazılamadı")
        except Exception:
            pass


_last_update_id = _load_last_update_id()
# PERSISTENT_TELEGRAM_OFFSET_PATCH_V1_END
def _tg(method, **data):
    r = requests.post(f"{API}/{method}", data=data, timeout=20)
    r.raise_for_status()
    return r.json()


def _send_to_chat(chat_id: str, text: str) -> None:
    _tg("sendMessage", chat_id=str(chat_id), text=str(text))


_commands_synced = False


def sync_telegram_commands() -> None:
    global _commands_synced
    if _commands_synced:
        return

    import json

    commands = [
        {"command": command, "description": description}
        for command, description in BOTFATHER_COMMANDS
    ]

    _tg(
        "setMyCommands",
        commands=json.dumps(commands, ensure_ascii=False),
        scope=json.dumps({"type": "chat", "chat_id": int(ADMIN_CHAT_ID)}),
    )

    _tg(
        "setMyCommands",
        commands="[]",
        scope=json.dumps({"type": "chat", "chat_id": int(GROUP_CHAT_ID)}),
    )

    _commands_synced = True
    logging.info("Telegram command menu synced")



def _restart_process(delay_seconds=1.5):
    def do_restart():
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Timer(delay_seconds, do_restart).start()


def _parse_minutes(value: str) -> int | None:
    value = str(value).strip().lower()
    if not value:
        return None
    try:
        if value.endswith("m"):
            return int(float(value[:-1]))
        if value.endswith("h"):
            return int(float(value[:-1]) * 60)
        return int(float(value))
    except Exception:
        return None


def _parse_seconds(value: str) -> int | None:
    value = str(value).strip().lower()
    if not value:
        return None
    try:
        if value.endswith("s"):
            seconds = int(float(value[:-1]))
        elif value.endswith("m"):
            seconds = int(float(value[:-1]) * 60)
        elif value.endswith("h"):
            seconds = int(float(value[:-1]) * 3600)
        else:
            seconds = int(float(value))
        return max(10, min(300, seconds))
    except Exception:
        return None


def _safe_float(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def _safe_int(value: str) -> int | None:
    try:
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return None


def build_status():
    cfg = load_config()
    active_modes = get_active_modes(cfg)

    scalp = bool(cfg["modes"].get("scalp"))
    intraday = bool(cfg["modes"].get("intraday"))
    midterm = bool(cfg["modes"].get("midterm"))

    if (not scalp) and intraday and midterm:
        mode_note = "Normal düzen: Intraday + Midterm aktif. Scalp manuel kapalı."
    elif scalp and intraday and midterm:
        mode_note = "Scalp dahil 3 mod aktif."
    else:
        mode_note = "Açık modlara göre çalışıyor."

    return (
        "📊 BOT DURUMU\n\n"
        f"Bot aktif: {'✅' if cfg.get('bot_active') else '❌'}\n"
        f"Kill switch: {'🚨 AÇIK' if cfg.get('kill_switch') else '✅ Kapalı'}\n"
        f"Sessiz mod: {'🔕 Açık' if cfg.get('notifications', {}).get('quiet_mode') else '🔔 Kapalı'}\n\n"
        "🧭 MODLAR\n"
        f"Scalp: {'✅' if scalp else '❌'}\n"
        f"Intraday: {'✅' if intraday else '❌'}\n"
        f"Midterm: {'✅' if midterm else '❌'}\n"
        f"Aktif çalışan: {', '.join(active_modes) or 'Yok'}\n"
        f"Not: {mode_note}\n\n"
        "🧪 FİLTRELER\n"
        f"Fake breakout: {'✅' if cfg['filters'].get('fake_breakout_filter') else '❌'}\n"
        f"Volume: {'✅' if cfg['filters'].get('volume_confirmation') else '❌'}\n"
        f"Min RR: {cfg['filters'].get('min_rr')}\n"
        f"Cooldown: {cfg['limits'].get('cooldown_minutes')} dk\n"
        f"Notify only: {cfg['notifications'].get('notify_only')}"
    )



def _read_tail(path: Path, lines=40) -> str:
    if not path.exists():
        return "Dosya bulunamadı."
    data = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(data[-lines:])[-3500:]


def _help_text():
    return (
        "🧭 MEXC TARAMA KOMUTLARI\n\n"

        "📊 Durum\n"
        "/status /ping /health /log /error_log\n\n"

        "⏱ Tarama\n"
        "🤖 Bot\n"
        "/start /stop /restart\n\n"

        "🧭 Modlar\n"
        "/modes /scalp_on /scalp_off\n\n"

        "🧪 Filtreler\n"
        "/fake_filter_on /fake_filter_off\n"
        "/volume_filter_on /volume_filter_off\n\n"

        "📌 Semboller\n"
        "/add_symbol BTCUSDT /remove_symbol BTCUSDT\n\n"

        "📈 Analiz\n"
        "📦 Güncelleme\n"
        "Not: Tarama mum kapanışına göre çalışır. /schedule yaz."
    )

def handle_command_message(message, send_telegram):
    chat_id = str(message.get("chat", {}).get("id", ""))

    text = message.get("text", "").strip()
    cmd = text.split()[0].lower() if text.startswith("/") else ""
    cmd = cmd.split("@", 1)[0]

    is_admin_private = chat_id == ADMIN_CHAT_ID
    is_group_chat = chat_id == GROUP_CHAT_ID

    if not is_admin_private and not is_group_chat:
        logging.warning("Yetkisiz Telegram mesaj? reddedildi: chat_id=%s", chat_id)
        return

    if is_group_chat and cmd not in GROUP_SAFE_COMMANDS:
        logging.warning(
            "Group-safe olmayan komut reddedildi: chat_id=%s cmd=%s",
            chat_id,
            cmd,
        )
        return

    cfg = load_config()

    def reply(reply_text: str) -> None:
        _send_to_chat(chat_id, reply_text)

    text = message.get("text", "").strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].lower()
    cmd = cmd.split("@", 1)[0]

    if is_admin_private and cmd not in ADMIN_PRIVATE_COMMANDS:
        logging.warning("Admin registry disi komut reddedildi: chat_id=%s cmd=%s", chat_id, cmd)
        reply("Bilinmeyen komut. /help yaz.")
        return



    if cmd == "/help":
        reply(_help_text())
        return

    if cmd == "/ping":
        reply("🏓 pong")
        return

    if cmd == "/health":
        reply(build_health_text())
        return

    if cmd == "/status":
        reply(build_status())
        return

    if cmd == "/scan_now":
        cfg.setdefault("runtime", {})["force_scan_once"] = True
        save_config(cfg)
        reply("⚡ Manuel tarama başlatıldı. Bekleme kesildi; bot uygunsa hemen taramaya geçiyor.")
        return

    if cmd == "/start":
        cfg["bot_active"] = True
        cfg["kill_switch"] = False
        cfg.setdefault("notifications", {})["quiet_mode"] = False
        save_config(cfg)
        reply("✅ Bot başlatıldı. Sinyal üretimi aktif.")
        return

    if cmd == "/stop":
        cfg["bot_active"] = False
        save_config(cfg)
        reply("⛔ Bot durduruldu. Sinyal üretimi kapalı.")
        return

    if cmd == "/restart":
        reply("♻️ Bot yeniden başlatılıyor...")
        _restart_process()
        return

    if cmd == "/modes":
        active_modes = get_active_modes(cfg)
        reply(
            "🧭 MODLAR\n\n"
            f"Scalp: {'✅' if cfg['modes'].get('scalp') else '❌'}\n"
            f"Intraday: {'✅' if cfg['modes'].get('intraday') else '❌'}\n"
            f"Midterm: {'✅' if cfg['modes'].get('midterm') else '❌'}\n\n"
            f"Aktif çalışan: {', '.join(active_modes) or 'Yok'}\n"
            "Detaylı zaman planı: /schedule"
        )
        return


    if cmd in ["/scalp_on", "/scalp_off"]:
        state = cmd.strip("/").split("_")[1]
        cfg.setdefault("modes", {})["scalp"] = state == "on"
        save_config(cfg)
        reply(f"Scalp mode {'enabled' if state == 'on' else 'disabled'}.")
        return

    if cmd == "/filters":
        reply(
            "🧪 FİLTRELER\n\n"
            f"Fake breakout: {'✅' if cfg['filters'].get('fake_breakout_filter') else '❌'}\n"
            f"Volume: {'✅' if cfg['filters'].get('volume_confirmation') else '❌'}\n"
            f"Min RR: {cfg['filters'].get('min_rr')}"
        )
        return

    if cmd == "/fake_filter_on":
        cfg.setdefault("filters", {})["fake_breakout_filter"] = True
        save_config(cfg)
        reply("✅ Fake breakout filtresi açıldı.")
        return

    if cmd == "/fake_filter_off":
        cfg.setdefault("filters", {})["fake_breakout_filter"] = False
        save_config(cfg)
        reply("⚠️ Fake breakout filtresi kapatıldı.")
        return

    if cmd == "/volume_filter_on":
        cfg.setdefault("filters", {})["volume_confirmation"] = True
        save_config(cfg)
        reply("✅ Volume filtresi açıldı.")
        return

    if cmd == "/volume_filter_off":
        cfg.setdefault("filters", {})["volume_confirmation"] = False
        save_config(cfg)
        reply("⚠️ Volume filtresi kapatıldı.")
        return
        value = _safe_float(parts[1])
        if value is None or value <= 0:
            reply("Geçersiz RR değeri.")
            return
        cfg.setdefault("filters", {})["min_rr"] = value
        save_config(cfg)
        reply(f"✅ Minimum RR: {value}")
        return

    if cmd == "/watchlist":
        symbols = cfg.get("watchlist", {}).get("symbols", [])
        if symbols:
            reply(
                "📌 İZLEME LİSTESİ\n\n"
                f"Taranacak semboller: {', '.join(symbols)}\n\n"
                "Not: Bot sadece bu listedeki sembolleri tarar."
            )
        else:
            reply(
                "📌 İZLEME LİSTESİ\n\n"
                "Liste boş. Bot tarama yapmaz.\n\n"
                "Sembol eklemek için: /add_symbol BTCUSDT"
            )
        return

    if cmd == "/add_symbol":
        if len(parts) < 2:
            reply("Kullanım: /add_symbol BTCUSDT")
            return

        symbol = normalize_symbol(parts[1])

        try:
            valid_symbols = set(get_valid_futures_symbols())
        except Exception as e:
            logging.exception("Sembol doğrulama hatası")
            reply(f"❌ Borsa sembol listesi alınamadı. Daha sonra tekrar dene. Hata: {str(e)[:120]}")
            return

        if symbol not in valid_symbols:
            reply(
                f"❌ Sembol eklenmedi: {symbol}\n"
                "Bu çift güncel futures listesinde görünmüyor."
            )
            return

        cfg.setdefault("watchlist", {}).setdefault("symbols", [])

        if symbol in cfg["watchlist"]["symbols"]:
            reply(f"ℹ️ Sembol zaten listede: {symbol}")
            return

        cfg["watchlist"]["symbols"].append(symbol)
        save_config(cfg)
        reply(f"✅ Sembol eklendi: {symbol}")
        return

    if cmd == "/remove_symbol":
        if len(parts) < 2:
            reply("Kullanım: /remove_symbol BTCUSDT")
            return
        symbol = normalize_symbol(parts[1])
        cfg.setdefault("watchlist", {}).setdefault("symbols", [])
        cfg["watchlist"]["symbols"] = [s for s in cfg["watchlist"]["symbols"] if s != symbol]
        save_config(cfg)
        reply(f"🗑 Sembol çıkarıldı: {symbol}")
        return

    if cmd == "/performance_today":
        reply(build_performance_today_text())
        return

    if cmd == "/log":
        reply("📜 SON LOG\n\n" + _read_tail(BASE_DIR / "logs" / "app.log", 25))
        return

    if cmd == "/error_log":
        raw = _read_tail(BASE_DIR / "logs" / "app.log", 250)
        lines = raw.splitlines()
        important = [ln for ln in lines if any(x in ln for x in ["ERROR", "Traceback", "Exception"])]

        if important:
            reply("🚨 HATA LOG\n\n" + "\n".join(important[-30:]))
        else:
            reply("✅ Son loglarda kritik hata yok.")
        return


    reply("Bilinmeyen komut. /help yaz.")
def poll_telegram_commands(send_telegram):
    try:
        sync_telegram_commands()
    except Exception:
        logging.exception("Telegram command sync failed")

    # TELEGRAM_COMMAND_THREAD_PATCH_V1: non-overlapping getUpdates with persistent offset.
    global _last_update_id
    if not _telegram_poll_lock.acquire(blocking=False):
        return
    try:
        params = {
            "timeout": 0,
            "allowed_updates": ["message"],
        }
        if _last_update_id:
            params["offset"] = _last_update_id + 1

        r = requests.get(f"{API}/getUpdates", params=params, timeout=6)
        try:
            data = r.json()
        except Exception:
            logging.exception("Telegram getUpdates JSON parse hatası")
            return

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
                text = str(message.get("text") or "").strip()
                if text:
                    logging.info("Telegram komut alındı: %s", text.split()[0])
                handle_command_message(message, send_telegram)
    except Exception as e:
        logging.exception("Telegram komut kontrol hatası: %s", e)
    finally:
        try:
            _telegram_poll_lock.release()
        except RuntimeError:
            pass


