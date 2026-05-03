import datetime as dt
import json
import logging
import os
import socket
import time
from pathlib import Path

from config import APP_LOG_PATH, REQUESTED_SYMBOLS
from core.state_store import load_state, save_state
from core.scanner import get_active_symbols, build_signal_message, get_daily_commentaries
from core.performance_tracker import finalize_pending_signals
from core.exchange_client import fetch_klines, get_kline_limit
from core.scheduler import next_sleep_seconds
from notifiers.telegram_notifier import send_telegram

from remote_config import load_config, save_config
from signal_journal import append_signal_message, set_last_signal
from single_instance import single_instance


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
SYMBOL_CACHE_PATH = STORAGE_DIR / "last_active_symbols.json"

STARTUP_SYMBOL_ATTEMPTS = 3
STARTUP_SYMBOL_RETRY_SECONDS = 10
SYMBOL_REFRESH_SECONDS = 300
DEGRADED_REMINDER_SECONDS = 1800


LOG_LEVEL = os.getenv("MEXC_LOG_LEVEL", "INFO").upper()
LOG_LEVEL_VALUE = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    filename=APP_LOG_PATH,
    level=LOG_LEVEL_VALUE,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


def _now_text():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _pc_user_text():
    pc = os.getenv("COMPUTERNAME") or socket.gethostname() or "?"
    user = os.getenv("USERNAME") or os.getenv("USER") or "?"
    return f"{pc}/{user}"


def _send_lifecycle(title, fields=None):
    if "Bot sureci basladi" in str(title) or "Process basladi" in str(title):
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
        logging.warning("Lifecycle Telegram mesaji gonderilemedi: %s", e)


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
        logging.warning("Sembol cache yazilamadi: %s", e)


def _load_symbol_cache():
    try:
        if not SYMBOL_CACHE_PATH.exists():
            return [], None
        data = json.loads(SYMBOL_CACHE_PATH.read_text(encoding="utf-8-sig"))
        symbols = _safe_symbols(data.get("symbols", []))
        saved_at = data.get("saved_at")
        return symbols, saved_at
    except Exception as e:
        logging.warning("Sembol cache okunamadi: %s", e)
        return [], None


def _default_fallback_symbols():
    return _safe_symbols(REQUESTED_SYMBOLS)


def _fetch_live_symbols_once():
    symbols = _safe_symbols(get_active_symbols())
    if not symbols:
        raise RuntimeError("Aktif sembol listesi bos geldi")
    return symbols


def load_symbols_resilient():
    last_error = None

    for attempt in range(1, STARTUP_SYMBOL_ATTEMPTS + 1):
        try:
            symbols = _fetch_live_symbols_once()
            _save_symbol_cache(symbols, source="live")
            logging.info("Aktif semboller alindi: %s adet", len(symbols))
            _send_lifecycle(
                "Bot calisiyor",
                {
                    "Tarama durumu": "Basladi",
                    "Gecerli borsa sembol sayisi": len(symbols),
                },
            )
            return symbols, False, time.time()
        except Exception as e:
            last_error = e
            logging.exception(
                "Aktif semboller alinamadi, startup denemesi %s/%s: %s",
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
        fallback = ["BTCUSDT", "ETHUSDT"]
        source = "hardcoded emergency fallback"

    logging.warning(
        "Aktif sembol listesi alinamadi; fallback sembollerle devam ediliyor | kaynak=%s | sembol=%s | hata=%s",
        source,
        ", ".join(fallback),
        last_error,
    )
    _send_lifecycle(
        "Bot basladi ama borsa sembol listesi alinamadi",
        {
            "Durum": "Fallback sembollerle tarama surecek",
            "Kaynak": source,
            "Sembol sayisi": len(fallback),
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
                "Borsa sembol listesi tekrar alindi",
                {
                    "Durum": "Normal tarama moduna donuldu",
                    "Sembol sayisi": len(symbols),
                    "Kaynak": "live",
                },
            )
        return symbols, False, now, 0

    except Exception as e:
        logging.exception("Aktif sembol listesi yenilenemedi; mevcut/fallback listeyle devam: %s", e)
        if not degraded:
            _send_lifecycle(
                "Borsa sembol listesi yenilenemedi",
                {
                    "Durum": "Son bilinen sembol listesiyle tarama surecek",
                    "Sembol sayisi": len(current_symbols),
                    "Son hata": str(e)[:220],
                },
            )
            last_degraded_notice = now
        elif now - last_degraded_notice >= DEGRADED_REMINDER_SECONDS:
            _send_lifecycle(
                "Borsa sembol listesi hala alinamiyor",
                {
                    "Durum": "Fallback/son bilinen listeyle tarama suruyor",
                    "Sembol sayisi": len(current_symbols),
                    "Son hata": str(e)[:220],
                },
            )
            last_degraded_notice = now
        return current_symbols, True, now, last_degraded_notice


def bot_allowed_to_scan():
    cfg = load_config()

    if not cfg.get("bot_active", True):
        return False

    if cfg.get("kill_switch", False):
        return False

    return True


def is_quiet_mode():
    cfg = load_config()
    return bool(cfg.get("notifications", {}).get("quiet_mode", False))


def consume_force_scan_request():
    try:
        cfg = load_config()
        runtime = cfg.setdefault("runtime", {})
        if runtime.get("force_scan_once"):
            runtime["force_scan_once"] = False
            save_config(cfg)
            logging.info("force_scan_once istegi alindi; tarama hemen calistirilacak")
            return True
    except Exception as e:
        logging.exception("force_scan_once kontrol hatasi: %s", e)
    return False


def apply_watchlist_filter(discovered_symbols):
    cfg = load_config()
    wanted = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))

    if not wanted:
        logging.warning("Watchlist bos; tarama yapilmayacak.")
        return []

    discovered = set(_safe_symbols(discovered_symbols))
    selected = [s for s in wanted if s in discovered]

    missing = [s for s in wanted if s not in discovered]
    if missing:
        logging.warning("Watchlist icinde borsada dogrulanamayan semboller var: %s", ", ".join(missing))

    return selected


def sleep_until_next_scan(seconds):
    time.sleep(max(1, int(seconds)))


def main():
    state = load_state()

    logging.info("Bot basladi")
    _send_lifecycle(
        "Bot sureci basladi / ayaga kalkti",
        {
            "Durum": "Process basladi",
        },
    )

    discovered_symbols, symbol_degraded, last_symbol_refresh = load_symbols_resilient()
    last_degraded_notice = time.time() if symbol_degraded else 0

    symbols = apply_watchlist_filter(discovered_symbols)
    logging.info("Tarama sembolleri: %s", ", ".join(symbols))

    while True:
        try:
            consume_force_scan_request()

            discovered_symbols, symbol_degraded, last_symbol_refresh, last_degraded_notice = maybe_refresh_symbols(
                discovered_symbols,
                symbol_degraded,
                last_symbol_refresh,
                last_degraded_notice,
            )

            symbols = apply_watchlist_filter(discovered_symbols)

            if bot_allowed_to_scan():
                signal_message = build_signal_message(symbols, state)

                if signal_message and signal_message != state.get("last_sent_message"):
                    set_last_signal(signal_message)
                    append_signal_message(signal_message)

                    if not is_quiet_mode():
                        send_telegram(signal_message)
                        logging.info("Yeni sinyal mesaji gonderildi")
                    else:
                        logging.info("Quiet mode acik; sinyal kaydedildi ama gonderilmedi")

                    state["last_sent_message"] = signal_message

                if not is_quiet_mode():
                    commentaries = get_daily_commentaries(symbols, state)
                    for msg in commentaries:
                        send_telegram(msg)
                        logging.info("Gunluk yorum gonderildi")
                else:
                    logging.info("Quiet mode acik; gunluk yorum gonderimi atlandi")

                finalize_pending_signals(state, fetch_klines, get_kline_limit)
                save_state(state)

            else:
                logging.info("Tarama atlandi: bot pasif veya kill switch acik")

        except Exception as e:
            logging.exception("Ana dongu hatasi: %s", e)

        sleep_until_next_scan(next_sleep_seconds())


if __name__ == "__main__":
    with single_instance("alarm_bot", BASE_DIR / "storage" / "alarm_bot.lock"):
        main()
