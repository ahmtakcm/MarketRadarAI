from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

import requests

from core.asset_universe import build_watchlist_text, resolve_asset_universe
from core.market_data_service import get_valid_futures_symbols
from core.symbol_resolver import SymbolResolver
from health_monitor import build_health_text
from remote_config import get_active_modes, load_config, normalize_symbol, update_config
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
    "/health",
    "/status",
    "/scan_now",
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
    ("help", "Komut listesi"),
    ("health", "Sistem sagligi"),
    ("status", "Bot durumu"),
    ("scan_now", "Anlik tarama"),
    ("restart", "Bot process restart"),
    ("modes", "Mod durumu"),
    ("scalp_on", "Scalp ac"),
    ("scalp_off", "Scalp kapat"),
    ("filters", "Filtre durumu"),
    ("fake_filter_on", "Fake filtre ac"),
    ("fake_filter_off", "Fake filtre kapat"),
    ("volume_filter_on", "Volume filtre ac"),
    ("volume_filter_off", "Volume filtre kapat"),
    ("watchlist", "Izleme listesi"),
    ("add_symbol", "Sembol ekle"),
    ("remove_symbol", "Sembol cikar"),
    ("performance_today", "Gunluk performans"),
    ("log", "Son loglar"),
    ("error_log", "Hata loglari"),
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
            logging.warning("Telegram offset okunamadÄ±")
        except Exception:
            pass
    return 0


def _save_last_update_id(update_id: int) -> None:
    try:
        _OFFSET_FILE.write_text(str(int(update_id)), encoding="utf-8")
    except Exception:
        try:
            logging.exception("Telegram offset dosyasÄ± yazÄ±lamadÄ±")
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
        mode_note = "Normal duzen: Intraday + Midterm aktif. Scalp manuel kapali."
    elif scalp and intraday and midterm:
        mode_note = "Scalp dahil 3 mod aktif."
    else:
        mode_note = "Acik modlara gore calisiyor."

    return (
        "BOT DURUMU\n\n"
        "Ping: pong\n\n"
        "MODLAR\n"
        f"Scalp: {'ON' if scalp else 'OFF'}\n"
        f"Intraday: {'ON' if intraday else 'OFF'}\n"
        f"Midterm: {'ON' if midterm else 'OFF'}\n"
        f"Aktif calisan: {', '.join(active_modes) or 'Yok'}\n"
        f"Not: {mode_note}\n\n"
        "FILTRELER\n"
        f"Fake breakout: {'ON' if cfg['filters'].get('fake_breakout_filter') else 'OFF'}\n"
        f"Volume: {'ON' if cfg['filters'].get('volume_confirmation') else 'OFF'}\n"
        f"Cooldown: {cfg['limits'].get('cooldown_minutes')} dk"
    )


def _read_tail(path: Path, lines=40) -> str:
    if not path.exists():
        return "Dosya bulunamadÄ±."
    data = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(data[-lines:])[-3500:]


def _help_text():
    return (
        "MarketRadarAI KOMUTLARI\n"
        "=======================\n\n"

        "[1] DURUM\n"
        "/status      Bot durumu + ping\n"
        "/health      Sistem sagligi\n"
        "/log         Son loglar\n"
        "/error_log   Hata loglari\n\n"

        "[2] TARAMA\n"
        "/scan_now    Aktif modlari mum kapanisi beklemeden tara\n\n"

        "[3] BOT\n"
        "/restart     Bot process yeniden baslat\n\n"

        "[4] MODLAR\n"
        "/modes       Aktif modlari goster\n"
        "/scalp_on    Scalp modunu ac\n"
        "/scalp_off   Scalp modunu kapat\n\n"

        "[5] FILTRELER\n"
        "/filters             Filtre durumunu goster\n"
        "/fake_filter_on      Fake breakout filtresini ac\n"
        "/fake_filter_off     Fake breakout filtresini kapat\n"
        "/volume_filter_on    Volume filtresini ac\n"
        "/volume_filter_off   Volume filtresini kapat\n\n"

        "[6] WATCHLIST\n"
        "/watchlist              Izleme listesini goster\n"
        "/add_symbol BTCUSDT     Sembol ekle\n"
        "/remove_symbol BTCUSDT  Sembol cikar\n\n"

        "[7] RAPOR\n"
        "/performance_today   Gunluk sinyal raporu\n\n"

        "Not: Grup komutlari kapali. Tum komutlar admin private chat icindir."
    )


def _watchlist_text(cfg):
    symbols = cfg.get("watchlist", {}).get("symbols", [])
    if not symbols:
        return (
            "MarketRadarAI WATCHLIST\n\n"
            "Liste bos. Bot tarama yapmaz.\n\n"
            "Sembol eklemek icin: /add_symbol BTCUSDT"
        )

    try:
        valid_symbols = get_valid_futures_symbols()
    except Exception as e:
        logging.exception("Watchlist symbol resolution failed")
        return (
            "MarketRadarAI WATCHLIST\n\n"
            f"Toplam: {len(symbols)}\n"
            f"Kayitli semboller: {', '.join(symbols)}\n\n"
            "Desteklenen/desteklenmeyen ayrimi su an dogrulanamadi.\n"
            f"Hata: {str(e)[:120]}"
        )

    return build_watchlist_text(resolve_asset_universe(symbols, valid_symbols))


def _set_config_value(section: str, key: str, value) -> None:
    def mutate(current):
        current.setdefault(section, {})[key] = value

    update_config(mutate)


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

    if cmd == "/health":
        reply(build_health_text())
        return

    if cmd == "/status":
        reply(build_status())
        return

    if cmd == "/scan_now":
        _set_config_value("runtime", "force_scan_once", True)
        reply("Anlik tarama tetiklendi. Aktif modlar icin mum kapanisi beklenmeden tarama baslatiliyor.")
        return

    if cmd == "/restart":
        reply("Bot process yeniden baslatiliyor...")
        _restart_process()
        return

    if cmd == "/modes":
        active_modes = get_active_modes(cfg)
        reply(
            "MODLAR\n\n"
            f"Scalp: {'ON' if cfg['modes'].get('scalp') else 'OFF'}\n"
            f"Intraday: {'ON' if cfg['modes'].get('intraday') else 'OFF'}\n"
            f"Midterm: {'ON' if cfg['modes'].get('midterm') else 'OFF'}\n\n"
            f"Aktif calisan: {', '.join(active_modes) or 'Yok'}\n"
            "Not: /scan_now aktif modlari anlik tarar."
        )
        return

    if cmd in ["/scalp_on", "/scalp_off"]:
        state = cmd.strip("/").split("_")[1]
        _set_config_value("modes", "scalp", state == "on")
        reply(f"Scalp mode {'enabled' if state == 'on' else 'disabled'}.")
        return

    if cmd == "/filters":
        reply(
            "FILTRELER\n\n"
            f"Fake breakout: {'ON' if cfg['filters'].get('fake_breakout_filter') else 'OFF'}\n"
            f"Volume: {'ON' if cfg['filters'].get('volume_confirmation') else 'OFF'}"
        )
        return

    if cmd == "/fake_filter_on":
        _set_config_value("filters", "fake_breakout_filter", True)
        reply("Fake breakout filtresi acildi.")
        return

    if cmd == "/fake_filter_off":
        _set_config_value("filters", "fake_breakout_filter", False)
        reply("Fake breakout filtresi kapatildi.")
        return

    if cmd == "/volume_filter_on":
        _set_config_value("filters", "volume_confirmation", True)
        reply("Volume filtresi acildi.")
        return

    if cmd == "/volume_filter_off":
        _set_config_value("filters", "volume_confirmation", False)
        reply("Volume filtresi kapatildi.")
        return

    if cmd == "/watchlist":
        reply(_watchlist_text(cfg))
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

        resolution = SymbolResolver().resolve(symbol, valid_symbols)
        if not resolution.supported or not resolution.resolved:
            reply(
                f"❌ Sembol eklenmedi: {symbol}\n"
                "Bu çift güncel futures listesinde görünmüyor."
            )
            return

        resolved_symbol = resolution.resolved
        result = {"already_present": False}

        def add_symbol(current):
            symbols = current.setdefault("watchlist", {}).setdefault("symbols", [])
            if resolved_symbol in symbols:
                result["already_present"] = True
                return
            symbols.append(resolved_symbol)

        update_config(add_symbol)

        if result["already_present"]:
            reply(f"ℹ️ Sembol zaten listede: {resolved_symbol}")
            return

        if resolved_symbol != symbol:
            reply(f"✅ Sembol eklendi: {symbol} -> {resolved_symbol}")
        else:
            reply(f"✅ Sembol eklendi: {resolved_symbol}")
        return

    if cmd == "/remove_symbol":
        if len(parts) < 2:
            reply("KullanÄ±m: /remove_symbol BTCUSDT")
            return
        symbol = normalize_symbol(parts[1])

        def remove_symbol(current):
            current.setdefault("watchlist", {}).setdefault("symbols", [])
            current["watchlist"]["symbols"] = [
                item for item in current["watchlist"]["symbols"] if item != symbol
            ]

        update_config(remove_symbol)
        reply(f"ğŸ—‘ Sembol Ã§Ä±karÄ±ldÄ±: {symbol}")
        return

    if cmd == "/performance_today":
        reply(build_performance_today_text())
        return

    if cmd == "/log":
        reply("ğŸ“œ SON LOG\n\n" + _read_tail(BASE_DIR / "logs" / "app.log", 25))
        return

    if cmd == "/error_log":
        raw = _read_tail(BASE_DIR / "logs" / "app.log", 250)
        lines = raw.splitlines()
        important = [ln for ln in lines if any(x in ln for x in ["ERROR", "Traceback", "Exception"])]

        if important:
            reply("ğŸš¨ HATA LOG\n\n" + "\n".join(important[-30:]))
        else:
            reply("âœ… Son loglarda kritik hata yok.")
        return


    reply("Bilinmeyen komut. /help yaz.")
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
            logging.exception("Telegram getUpdates JSON parse hatasÄ±")
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
                    logging.info("Telegram command received: %s", text.split()[0])
                handle_command_message(message, send_telegram)
    except Exception as e:
        logging.exception("Telegram komut kontrol hatasÄ±: %s", e)
    finally:
        try:
            _telegram_poll_lock.release()
        except RuntimeError:
            pass



