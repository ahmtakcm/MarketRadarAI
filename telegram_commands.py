from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

import requests

from core.exchange_client import get_valid_futures_symbols
from core.scheduler import build_schedule_text
from health_monitor import build_health_text
from remote_config import get_active_modes, load_config, normalize_symbol, save_config
from signal_journal import build_performance_today_text, get_last_signal
from update_manager import INBOX_DIR, apply_update, rollback

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

GROUP_SAFE_COMMANDS = {
    "/help",
    "/ping",
    "/status",
    "/health",
    "/schedule",
    "/watchlist",
}

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


def _download_file(file_id, filename):
    info = _tg("getFile", file_id=file_id)
    file_path = info["result"]["file_path"]

    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    target = INBOX_DIR / filename
    target.write_bytes(r.content)
    return target


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
        "/schedule /scan_now\n\n"

        "🤖 Bot\n"
        "/start /stop /restart\n\n"

        "🧭 Modlar\n"
        "/modes /scalp_on /scalp_off\n\n"

        "🧪 Filtreler\n"
        "/filters /set_min_rr\n"
        "/fake_filter_on /fake_filter_off\n"
        "/volume_filter_on /volume_filter_off\n\n"

        "📌 Semboller\n"
        "/symbols /watchlist\n"
        "/add_symbol BTCUSDT /remove_symbol BTCUSDT\n\n"

        "📈 Analiz\n"
        "/last_signal /performance_today\n\n"

        "📦 Güncelleme\n"
        "/update_zip /update_apply /update_status /rollback\n\n"

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

    # ZIP güncelleme akışı
    if "document" in message:
        if cfg.get("update", {}).get("last_status") != "waiting_zip":
            send_telegram("ZIP geldi ama /update_zip modu açık değil.")
            return

        doc = message["document"]
        filename = doc.get("file_name", "")

        if not filename.lower().endswith(".zip"):
            send_telegram("Sadece .zip dosyası kabul edilir.")
            return

        target = _download_file(doc["file_id"], filename)
        cfg.setdefault("update", {})["pending_zip"] = str(target)
        cfg.setdefault("update", {})["last_status"] = "zip_received"
        save_config(cfg)

        send_telegram(f"✅ ZIP alındı: {filename}\nUygulamak için /update_apply yaz.")
        return

    text = message.get("text", "").strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].lower()

    aliases = {
        "/komutlar": "/help",
        "/commands": "/help",
        "/alive": "/status",
        "/durum": "/status",
        "/start_bot": "/start",
        "/stop_bot": "/stop",
    }
    cmd = aliases.get(cmd, cmd)

    removed_cmds = {
        "/scan_interval", "/interval", "/set_interval", "/speed",
        "/kill_switch_on", "/kill_switch_off",
        "/mode_only", "/risk",
        "/set_cooldown", "/set_cooldown_symbol",
        "/set_max_signals", "/set_max_same_symbol",
        "/watch", "/unwatch",
        "/explain_on", "/explain_off",
        "/quiet_on", "/quiet_off",
        "/notify_only", "/explain_last",
        "/botfather_commands",
    }

    if cmd in removed_cmds:
        send_telegram("⚠️ Bu komut kaldırıldı. Güncel komutlar için /help yaz.")
        return

    if cmd == "/help":
        send_telegram(_help_text())
        return

    if cmd == "/ping":
        send_telegram("🏓 pong")
        return

    if cmd == "/health":
        send_telegram(build_health_text())
        return

    if cmd == "/status":
        send_telegram(build_status())
        return

    if cmd == "/schedule":
        send_telegram(build_schedule_text())
        return

    if cmd == "/scan_now":
        cfg.setdefault("runtime", {})["force_scan_once"] = True
        save_config(cfg)
        send_telegram("⚡ Manuel tarama başlatıldı. Bekleme kesildi; bot uygunsa hemen taramaya geçiyor.")
        return

    if cmd == "/start":
        cfg["bot_active"] = True
        cfg["kill_switch"] = False
        cfg.setdefault("notifications", {})["quiet_mode"] = False
        save_config(cfg)
        send_telegram("✅ Bot başlatıldı. Sinyal üretimi aktif.")
        return

    if cmd == "/stop":
        cfg["bot_active"] = False
        save_config(cfg)
        send_telegram("⛔ Bot durduruldu. Sinyal üretimi kapalı.")
        return

    if cmd == "/restart":
        send_telegram("♻️ Bot yeniden başlatılıyor...")
        _restart_process()
        return

    if cmd == "/modes":
        active_modes = get_active_modes(cfg)
        send_telegram(
            "🧭 MODLAR\n\n"
            f"Scalp: {'✅' if cfg['modes'].get('scalp') else '❌'}\n"
            f"Intraday: {'✅' if cfg['modes'].get('intraday') else '❌'}\n"
            f"Midterm: {'✅' if cfg['modes'].get('midterm') else '❌'}\n\n"
            f"Aktif çalışan: {', '.join(active_modes) or 'Yok'}\n"
            "Detaylı zaman planı: /schedule"
        )
        return

    if cmd in ["/scalp_on", "/scalp_off", "/intraday_on", "/intraday_off", "/midterm_on", "/midterm_off"]:
        name = cmd.strip("/").split("_")[0]
        state = cmd.strip("/").split("_")[1]
        cfg.setdefault("modes", {})[name] = state == "on"
        cfg["mode_only"] = None
        save_config(cfg)
        send_telegram(f"✅ {name} {'açıldı' if state == 'on' else 'kapatıldı'}.")
        return

    if cmd == "/filters":
        send_telegram(
            "🧪 FİLTRELER\n\n"
            f"Fake breakout: {'✅' if cfg['filters'].get('fake_breakout_filter') else '❌'}\n"
            f"Volume: {'✅' if cfg['filters'].get('volume_confirmation') else '❌'}\n"
            f"Min RR: {cfg['filters'].get('min_rr')}"
        )
        return

    if cmd == "/fake_filter_on":
        cfg.setdefault("filters", {})["fake_breakout_filter"] = True
        save_config(cfg)
        send_telegram("✅ Fake breakout filtresi açıldı.")
        return

    if cmd == "/fake_filter_off":
        cfg.setdefault("filters", {})["fake_breakout_filter"] = False
        save_config(cfg)
        send_telegram("⚠️ Fake breakout filtresi kapatıldı.")
        return

    if cmd == "/volume_filter_on":
        cfg.setdefault("filters", {})["volume_confirmation"] = True
        save_config(cfg)
        send_telegram("✅ Volume filtresi açıldı.")
        return

    if cmd == "/volume_filter_off":
        cfg.setdefault("filters", {})["volume_confirmation"] = False
        save_config(cfg)
        send_telegram("⚠️ Volume filtresi kapatıldı.")
        return

    if cmd == "/set_min_rr":
        if len(parts) < 2:
            send_telegram("Kullanım: /set_min_rr 1.5")
            return
        value = _safe_float(parts[1])
        if value is None or value <= 0:
            send_telegram("Geçersiz RR değeri.")
            return
        cfg.setdefault("filters", {})["min_rr"] = value
        save_config(cfg)
        send_telegram(f"✅ Minimum RR: {value}")
        return

    if cmd in ["/symbols", "/watchlist"]:
        symbols = cfg.get("watchlist", {}).get("symbols", [])
        if symbols:
            send_telegram(
                "📌 İZLEME LİSTESİ\n\n"
                f"Taranacak semboller: {', '.join(symbols)}\n\n"
                "Not: Bot sadece bu listedeki sembolleri tarar."
            )
        else:
            send_telegram(
                "📌 İZLEME LİSTESİ\n\n"
                "Liste boş. Bot tarama yapmaz.\n\n"
                "Sembol eklemek için: /add_symbol BTCUSDT"
            )
        return

    if cmd == "/add_symbol":
        if len(parts) < 2:
            send_telegram("Kullanım: /add_symbol BTCUSDT")
            return

        symbol = normalize_symbol(parts[1])

        try:
            valid_symbols = set(get_valid_futures_symbols())
        except Exception as e:
            logging.exception("Sembol doğrulama hatası")
            send_telegram(f"❌ Borsa sembol listesi alınamadı. Daha sonra tekrar dene. Hata: {str(e)[:120]}")
            return

        if symbol not in valid_symbols:
            send_telegram(
                f"❌ Sembol eklenmedi: {symbol}\n"
                "Bu çift güncel futures listesinde görünmüyor."
            )
            return

        cfg.setdefault("watchlist", {}).setdefault("symbols", [])

        if symbol in cfg["watchlist"]["symbols"]:
            send_telegram(f"ℹ️ Sembol zaten listede: {symbol}")
            return

        cfg["watchlist"]["symbols"].append(symbol)
        save_config(cfg)
        send_telegram(f"✅ Sembol eklendi: {symbol}")
        return

    if cmd == "/remove_symbol":
        if len(parts) < 2:
            send_telegram("Kullanım: /remove_symbol BTCUSDT")
            return
        symbol = normalize_symbol(parts[1])
        cfg.setdefault("watchlist", {}).setdefault("symbols", [])
        cfg["watchlist"]["symbols"] = [s for s in cfg["watchlist"]["symbols"] if s != symbol]
        save_config(cfg)
        send_telegram(f"🗑 Sembol çıkarıldı: {symbol}")
        return

    if cmd == "/last_signal":
        send_telegram(get_last_signal())
        return

    if cmd == "/performance_today":
        send_telegram(build_performance_today_text())
        return

    if cmd == "/log":
        send_telegram("📜 SON LOG\n\n" + _read_tail(BASE_DIR / "logs" / "app.log", 25))
        return

    if cmd == "/error_log":
        raw = _read_tail(BASE_DIR / "logs" / "app.log", 250)
        lines = raw.splitlines()
        important = [ln for ln in lines if any(x in ln for x in ["ERROR", "Traceback", "Exception"])]

        if important:
            send_telegram("🚨 HATA LOG\n\n" + "\n".join(important[-30:]))
        else:
            send_telegram("✅ Son loglarda kritik hata yok.")
        return

    if cmd == "/update_zip":
        cfg.setdefault("update", {})["last_status"] = "waiting_zip"
        save_config(cfg)
        send_telegram("📦 ZIP güncelleme modu açıldı. Şimdi ZIP dosyasını gönder.")
        return

    if cmd == "/update_status":
        update = cfg.get("update", {})
        send_telegram(
            "📦 GÜNCELLEME DURUMU\n\n"
            f"Durum: {update.get('last_status')}\n"
            f"Bekleyen ZIP: {update.get('pending_zip') or 'Yok'}"
        )
        return

    if cmd == "/update_apply":
        try:
            result = apply_update()
            send_telegram("✅ Güncelleme uygulandı. Bot yeniden başlatılıyor...\n\n" + str(result))
            _restart_process()
        except Exception as e:
            logging.exception("Update apply hatası")
            send_telegram(f"❌ Güncelleme hatası: {e}")
        return

    if cmd == "/rollback":
        try:
            result = rollback()
            send_telegram("♻️ Rollback uygulandı. Bot yeniden başlatılıyor...\n\n" + str(result))
            _restart_process()
        except Exception as e:
            logging.exception("Rollback hatası")
            send_telegram(f"❌ Rollback hatası: {e}")
        return

    send_telegram("Bilinmeyen komut. /help yaz.")
def poll_telegram_commands(send_telegram):
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


