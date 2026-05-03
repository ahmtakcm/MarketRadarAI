import datetime as dt
import logging
import os
import socket
import time
from pathlib import Path

from config import APP_LOG_PATH, REQUESTED_SYMBOLS
from core.state_store import load_state, save_state
from core.scanner import build_signal_message, get_daily_commentaries
from core.performance_tracker import finalize_pending_signals
from core.exchange_client import fetch_klines, get_kline_limit, validate_futures_symbol
from core.scheduler import next_sleep_seconds
from notifiers.telegram_notifier import send_telegram

from remote_config import load_config, save_config
from signal_journal import append_signal_message, set_last_signal
from single_instance import single_instance


BASE_DIR = Path(__file__).resolve().parent

STARTUP_SYMBOL_ATTEMPTS = 3
STARTUP_SYMBOL_RETRY_SECONDS = 10
SYMBOL_REFRESH_SECONDS = 300
DEGRADED_REMINDER_SECONDS = 1800
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]


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


def configured_scan_symbols():
    cfg = load_config()
    symbols = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    source = "remote_config.watchlist.symbols"

    if not symbols:
        symbols = _safe_symbols(REQUESTED_SYMBOLS)
        source = "settings.json symbols"

    if not symbols:
        symbols = list(DEFAULT_SYMBOLS)
        source = "hardcoded fallback"

    logging.info("Watchlist sembolleri: %s | kaynak=%s", ", ".join(symbols), source)
    return symbols, source


def validate_scan_symbols(symbols, tf="15m", min_candles=30):
    valid = []
    invalid = []

    for symbol in _safe_symbols(symbols):
        ok, reason = validate_futures_symbol(symbol, tf=tf, min_candles=min_candles)
        if ok:
            valid.append(symbol)
        else:
            invalid.append((symbol, reason))
            logging.warning("Watchlist sembolu gecersiz; atlandi | %s | %s", symbol, reason)

    return valid, invalid


def load_symbols_resilient():
    last_error = None

    for attempt in range(1, STARTUP_SYMBOL_ATTEMPTS + 1):
        try:
            configured, source = configured_scan_symbols()
            symbols, invalid = validate_scan_symbols(configured)
            if not symbols:
                raise RuntimeError("Gecerli watchlist sembolu bulunamadi")

            logging.info(
                "Watchlist dogrulandi: %s | gecersiz=%s | kaynak=%s",
                ", ".join(symbols),
                len(invalid),
                source,
            )
            _send_lifecycle(
                "Bot calisiyor",
                {
                    "Tarama durumu": "Basladi",
                    "Watchlist sembolleri": ", ".join(symbols),
                },
            )
            return symbols, False, time.time()
        except Exception as e:
            last_error = e
            logging.exception(
                "Watchlist dogrulanamadi, startup denemesi %s/%s: %s",
                attempt,
                STARTUP_SYMBOL_ATTEMPTS,
                e,
            )
            if attempt < STARTUP_SYMBOL_ATTEMPTS:
                time.sleep(STARTUP_SYMBOL_RETRY_SECONDS)

    fallback = list(DEFAULT_SYMBOLS)

    logging.warning(
        "Watchlist dogrulanamadi; minimum fallback sembollerle devam ediliyor | sembol=%s | hata=%s",
        ", ".join(fallback),
        last_error,
    )
    _send_lifecycle(
        "Bot basladi ama watchlist dogrulanamadi",
        {
            "Durum": "Minimum fallback sembollerle tarama surecek",
            "Watchlist sembolleri": ", ".join(fallback),
            "Son hata": str(last_error)[:220],
        },
    )
    return fallback, True, time.time()


def maybe_refresh_symbols(current_symbols, degraded, last_refresh, last_degraded_notice):
    now = time.time()
    if now - last_refresh < SYMBOL_REFRESH_SECONDS:
        return current_symbols, degraded, last_refresh, last_degraded_notice

    try:
        configured, source = configured_scan_symbols()
        symbols, invalid = validate_scan_symbols(configured)
        if not symbols:
            raise RuntimeError("Gecerli watchlist sembolu bulunamadi")

        logging.info(
            "Watchlist yenilendi: %s | gecersiz=%s | kaynak=%s",
            ", ".join(symbols),
            len(invalid),
            source,
        )
        if degraded:
            _send_lifecycle(
                "Watchlist tekrar dogrulandi",
                {
                    "Durum": "Normal tarama moduna donuldu",
                    "Watchlist sembolleri": ", ".join(symbols),
                },
            )
        return symbols, False, now, 0

    except Exception as e:
        logging.exception("Watchlist yenilenemedi; mevcut listeyle devam: %s", e)
        if not degraded:
            _send_lifecycle(
                "Watchlist yenilenemedi",
                {
                    "Durum": "Son bilinen sembol listesiyle tarama surecek",
                    "Watchlist sembolleri": ", ".join(current_symbols),
                    "Son hata": str(e)[:220],
                },
            )
            last_degraded_notice = now
        elif now - last_degraded_notice >= DEGRADED_REMINDER_SECONDS:
            _send_lifecycle(
                "Watchlist hala dogrulanamiyor",
                {
                    "Durum": "Son bilinen listeyle tarama suruyor",
                    "Watchlist sembolleri": ", ".join(current_symbols),
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

    symbols, symbol_degraded, last_symbol_refresh = load_symbols_resilient()
    last_degraded_notice = time.time() if symbol_degraded else 0

    logging.info("Tarama sembolleri: %s", ", ".join(symbols))

    while True:
        try:
            consume_force_scan_request()

            symbols, symbol_degraded, last_symbol_refresh, last_degraded_notice = maybe_refresh_symbols(
                symbols,
                symbol_degraded,
                last_symbol_refresh,
                last_degraded_notice,
            )

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
