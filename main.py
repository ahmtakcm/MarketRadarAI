import datetime as dt
import logging
import os
from pathlib import Path

from config import APP_LOG_PATH, STATE_FILE_PATH
from core.observability import build_startup_metadata, format_startup_metadata
from core.scanner_orchestrator import ScannerRuntime
from notifiers.telegram_notifier import send_telegram
from remote_config import get_active_modes, get_config_path, load_config
from single_instance import single_instance
from telegram_commands import poll_telegram_commands, sync_telegram_commands

BASE_DIR = Path(__file__).resolve().parent

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


def main():
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

    runtime = ScannerRuntime(
        send_telegram=send_telegram,
        poll_telegram_commands=poll_telegram_commands,
        send_lifecycle=_send_lifecycle,
        sync_telegram_commands=sync_telegram_commands,
    )
    runtime.run_forever()


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
