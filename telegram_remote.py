from __future__ import annotations

import logging
import time

from notifiers.telegram_notifier import send_telegram
from telegram_commands import poll_telegram_commands, telegram_polling_enabled


def run() -> None:
    if not telegram_polling_enabled():
        logging.info("Telegram remote polling disabled")
        return

    while True:
        poll_telegram_commands(send_telegram)
        time.sleep(2)


if __name__ == "__main__":
    run()
