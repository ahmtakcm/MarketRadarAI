import datetime as dt
import json
import logging
import os
import socket
import threading
import time
from pathlib import Path

from config import APP_LOG_PATH, REQUESTED_SYMBOLS, STATE_FILE_PATH
from core.exchange_client import fetch_klines, get_kline_limit
from core.observability import (
    build_scan_observation,
    build_startup_metadata,
    format_scan_observation,
    format_startup_metadata,
)
from core.performance_tracker import finalize_pending_signals
from core.scanner import build_signal_message, get_active_symbols, get_daily_commentaries
from core.scheduler import next_sleep_seconds
from core.state_store import load_state, save_state
from notifiers.telegram_notifier import send_telegram
from remote_config import get_active_modes, get_config_path, load_config, save_config
from signal_journal import append_signal_message, set_last_signal
from single_instance import single_instance
from telegram_commands import poll_telegram_commands

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
SYMBOL_CACHE_PATH = STORAGE_DIR / "last_active_symbols.json"

STARTUP_SYMBOL_ATTEMPTS = 3
STARTUP_SYMBOL_RETRY_SECONDS = 10
SYMBOL_REFRESH_SECONDS = 300
DEGRADED_REMINDER_SECONDS = 1800


LOG_LEVEL = os.getenv("MEXC_LOG_LEVEL", "INFO").upper()
LOG_LEVEL_VALUE = getattr(logging, LOG_LEVEL, logging.INFO)
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"

APP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=LOG_LEVEL_VALUE,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(APP_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def _now_text():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _pc_user_text():
    pc = os.getenv("COMPUTERNAME") or socket.gethostname() or "?"
    user = os.getenv("USERNAME") or os.getenv("USER") or "?"
    return f"{pc}/{user}"


def _send_lifecycle(title, fields=None):
    # Kullanıcıya gereksiz process/klasör/PC detayı gönderme.
    # Sadece tek ve sade başlangıç mesajı gönder.
    if "Bot süreci başladı" in str(title) or "Process başladı" in str(title):
        return

    fields = fields or {}
    lines = [title, ""]

    for key, value in fields.items():
        lines.append(f"{key}: {value}")

    lines.append(f"Zaman: {_now_text()}")

    text = "\n".join(lines)
    try:
        send_telegram(text)
    except Exception as e:
        logging.warning("Lifecycle Telegram mesajı gönderilemedi: %s", e)



def _safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        sym = str(value or "").upper().strip()
        if sym and sym not in seen:
            result.append(sym)
            seen.add(sym)
    return result


def _save_symbol_cache(symbols, source="live"):
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": _now_text(),
            "source": source,
            "symbols": _safe_symbols(symbols),
        }
        tmp = SYMBOL_CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, SYMBOL_CACHE_PATH)
    except Exception as e:
        logging.warning("Sembol cache yazılamadı: %s", e)


def _load_symbol_cache():
    try:
        if not SYMBOL_CACHE_PATH.exists():
            return [], None
        data = json.loads(SYMBOL_CACHE_PATH.read_text(encoding="utf-8-sig"))
        symbols = _safe_symbols(data.get("symbols", []))
        saved_at = data.get("saved_at")
        return symbols, saved_at
    except Exception as e:
        logging.warning("Sembol cache okunamadı: %s", e)
        return [], None


def _default_fallback_symbols():
    return _safe_symbols(REQUESTED_SYMBOLS)


def _fetch_live_symbols_once():
    symbols = _safe_symbols(get_active_symbols())
    if not symbols:
        raise RuntimeError("Aktif sembol listesi boş geldi")
    return symbols


def load_symbols_resilient():
    """
    Eski davranışta bot burada sonsuza kadar bekliyordu.
    Yeni davranış: birkaç deneme yap, olmazsa cache/default sembollerle taramaya devam et.
    """
    last_error = None

    for attempt in range(1, STARTUP_SYMBOL_ATTEMPTS + 1):
        try:
            symbols = _fetch_live_symbols_once()
            _save_symbol_cache(symbols, source="live")
            logging.info("Aktif semboller alındı: %s adet", len(symbols))
            _send_lifecycle(
                "✅ Bot çalışıyor",
                {
                    "Tarama durumu": "Başladı",
                    "Geçerli borsa sembol sayısı": len(symbols),
                },
            )
            return symbols, False, time.time()
        except Exception as e:
            last_error = e
            logging.exception(
                "Aktif semboller alınamadı, startup denemesi %s/%s: %s",
                attempt,
                STARTUP_SYMBOL_ATTEMPTS,
                e,
            )
            if attempt < STARTUP_SYMBOL_ATTEMPTS:
                time.sleep(STARTUP_SYMBOL_RETRY_SECONDS)

    cached_symbols, cached_at = _load_symbol_cache()
    if cached_symbols:
        fallback = cached_symbols
        source = f"cache ({cached_at or 'tarih yok'})"
    else:
        fallback = _default_fallback_symbols()
        source = "default settings.json symbols"

    if not fallback:
        # Son çare: en azından çekirdek sembollerle döngüyü başlat.
        fallback = ["BTCUSDT", "ETHUSDT", "XAUUSDT", "XAGUSDT"]
        source = "hardcoded emergency fallback"

    logging.warning(
        "Aktif sembol listesi alınamadı; fallback sembollerle devam ediliyor | kaynak=%s | sembol=%s | hata=%s",
        source,
        ", ".join(fallback),
        last_error,
    )
    _send_lifecycle(
        "⚠️ Bot başladı ama borsa sembol listesi alınamadı",
        {
            "Durum": "Fallback sembollerle tarama sürecek",
            "Kaynak": source,
            "Sembol sayısı": len(fallback),
            "Son hata": str(last_error)[:220],
        },
    )
    return fallback, True, time.time()


def maybe_refresh_symbols(current_symbols, degraded, last_refresh, last_degraded_notice):
    now = time.time()
    if now - last_refresh < SYMBOL_REFRESH_SECONDS:
        return current_symbols, degraded, last_refresh, last_degraded_notice

    try:
        symbols = _fetch_live_symbols_once()
        _save_symbol_cache(symbols, source="live")
        logging.info("Aktif sembol listesi yenilendi: %s adet", len(symbols))
        if degraded:
            _send_lifecycle(
                "✅ Borsa sembol listesi tekrar alındı",
                {
                    "Durum": "Normal tarama moduna dönüldü",
                    "Sembol sayısı": len(symbols),
                    "Kaynak": "live",
                },
            )
        return symbols, False, now, 0

    except Exception as e:
        logging.exception("Aktif sembol listesi yenilenemedi; mevcut/fallback listeyle devam: %s", e)
        if not degraded:
            _send_lifecycle(
                "⚠️ Borsa sembol listesi yenilenemedi",
                {
                    "Durum": "Son bilinen sembol listesiyle tarama sürecek",
                    "Sembol sayısı": len(current_symbols),
                    "Son hata": str(e)[:220],
                },
            )
            last_degraded_notice = now
        elif now - last_degraded_notice >= DEGRADED_REMINDER_SECONDS:
            _send_lifecycle(
                "⚠️ Borsa sembol listesi hâlâ alınamıyor",
                {
                    "Durum": "Fallback/son bilinen listeyle tarama sürüyor",
                    "Sembol sayısı": len(current_symbols),
                    "Son hata": str(e)[:220],
                },
            )
            last_degraded_notice = now
        return current_symbols, True, now, last_degraded_notice


def bot_allowed_to_scan():
    return True


def is_quiet_mode():
    return False


def consume_force_scan_request():
    try:
        cfg = load_config()
        runtime = cfg.setdefault("runtime", {})
        if runtime.get("force_scan_once"):
            runtime["force_scan_once"] = False
            save_config(cfg)
            watchlist_count = len(_safe_symbols(cfg.get("watchlist", {}).get("symbols", [])))
            logging.info(
                "Telegram /scan_now force_scan_once consumed | active_modes=%s | watchlist_count=%s",
                ",".join(get_active_modes(cfg)) or "-",
                watchlist_count,
            )
            logging.info("Telegram /scan_now isteği alındı; tarama hemen çalıştırılacak")
            return True
    except Exception as e:
        logging.exception("force_scan_once kontrol hatası: %s", e)
    return False


def apply_watchlist_filter(discovered_symbols):
    """
    Watchlist kesin kural:
    - Bot sadece watchlist.symbols listesindeki sembolleri tarar.
    - Liste boşsa tarama yapılmaz.
    - Tüm borsa/default sembol taraması yapılmaz.
    """
    cfg = load_config()
    wanted = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))

    if not wanted:
        logging.warning("Watchlist boş; tarama yapılmayacak.")
        return []

    discovered = set(_safe_symbols(discovered_symbols))
    selected = [s for s in wanted if s in discovered]

    missing = [s for s in wanted if s not in discovered]
    if missing:
        logging.warning("Watchlist içinde borsada doğrulanamayan semboller var: %s", ", ".join(missing))

    return selected



def sleep_with_command_polling(seconds):
    end_time = time.time() + max(1, int(seconds))

    while time.time() < end_time:
        try:
            poll_telegram_commands(send_telegram)
            cfg = load_config()
            if cfg.get("runtime", {}).get("force_scan_once"):
                logging.info("/scan_now bayrağı görüldü; uyku erken kesiliyor")
                return
        except Exception as e:
            logging.exception("Uyku sırasında Telegram komut okuma hatası: %s", e)

        time.sleep(1)



# TELEGRAM_COMMAND_THREAD_PATCH_V1_START
_telegram_command_thread_started = False


def _telegram_command_thread_loop():
    logging.info("Telegram komut thread'i başladı")
    while True:
        try:
            poll_telegram_commands(send_telegram)
        except Exception as e:
            logging.exception("Telegram komut thread hatası: %s", e)
        time.sleep(1.5)


def start_telegram_command_thread():
    global _telegram_command_thread_started
    if _telegram_command_thread_started:
        return
    t = threading.Thread(
        target=_telegram_command_thread_loop,
        name="telegram-command-poller",
        daemon=True,
    )
    t.start()
    _telegram_command_thread_started = True
# TELEGRAM_COMMAND_THREAD_PATCH_V1_END

def main():
    state = load_state()
    cfg = load_config()

    logging.info(
        format_startup_metadata(
            build_startup_metadata(cfg, get_active_modes(cfg), STATE_FILE_PATH, get_config_path())
        )
    )

    logging.info("Bot başladı")
    _send_lifecycle(
        "✅ Bot süreci başladı / ayağa kalktı",
        {
            "Durum": "Process başladı",
        },
    )

    start_telegram_command_thread()
    discovered_symbols, symbol_degraded, last_symbol_refresh = load_symbols_resilient()
    last_degraded_notice = time.time() if symbol_degraded else 0

    symbols = apply_watchlist_filter(discovered_symbols)
    logging.info("Tarama sembolleri: %s", ", ".join(symbols))
    logging.info("MarketRadarAI startup success | scan_symbol_count=%s", len(symbols))

    while True:
        try:
            consume_force_scan_request()
            # Telegram komutlarını ana bot içinde oku.
            # Ayrı telegram_remote.py çalıştırılmayacak.
            poll_telegram_commands(send_telegram)

            discovered_symbols, symbol_degraded, last_symbol_refresh, last_degraded_notice = maybe_refresh_symbols(
                discovered_symbols,
                symbol_degraded,
                last_symbol_refresh,
                last_degraded_notice,
            )

            # Watchlist değişmiş olabilir; her turda hafifçe uygula.
            symbols = apply_watchlist_filter(discovered_symbols)

            if bot_allowed_to_scan():
                loop_started_at = time.time()
                loop_cfg = load_config()
                scan_observation = build_scan_observation(get_active_modes(loop_cfg), symbols)
                logging.info(format_scan_observation("start", scan_observation))
                signal_message = build_signal_message(symbols, state)

                if signal_message and signal_message != state.get("last_sent_message"):
                    set_last_signal(signal_message)
                    append_signal_message(signal_message)

                    if not is_quiet_mode():
                        send_telegram(signal_message)
                        logging.info("Yeni sinyal mesajı gönderildi")
                    else:
                        logging.info("Quiet mode açık; sinyal kaydedildi ama gönderilmedi")

                    state["last_sent_message"] = signal_message

                if not is_quiet_mode():
                    commentaries = get_daily_commentaries(symbols, state)
                    for msg in commentaries:
                        send_telegram(msg)
                        logging.info("Günlük yorum gönderildi")
                else:
                    logging.info("Quiet mode açık; günlük yorum gönderimi atlandı")

                finalize_pending_signals(state, fetch_klines, get_kline_limit)
                save_state(state)
                logging.info(
                    "%s | duration_seconds=%.2f",
                    format_scan_observation("finish", scan_observation),
                    time.time() - loop_started_at,
                )

            else:
                logging.info("Tarama atlandı: bot pasif veya kill switch açık")

        except Exception as e:
            logging.exception("Ana döngü hatası: %s", e)

        sleep_with_command_polling(next_sleep_seconds())


if __name__ == "__main__":
    try:
        with single_instance("alarm_bot", BASE_DIR / "storage" / "alarm_bot.lock"):
            main()
    except KeyboardInterrupt:
        logging.info("MarketRadarAI shutdown requested by KeyboardInterrupt")
        raise
    except Exception:
        logging.exception("MarketRadarAI fatal crash")
        raise
