from __future__ import annotations

from telegram.messages import (
    build_health_text,
    build_performance_today_text,
    build_status,
    error_log_text,
    help_text,
    log_text,
)


def handle_help(reply) -> None:
    reply(help_text())


def handle_health(reply) -> None:
    reply(build_health_text())


def handle_status(reply) -> None:
    reply(build_status())


def handle_performance_today(reply) -> None:
    reply(build_performance_today_text())


def handle_log(reply) -> None:
    reply(log_text())


def handle_error_log(reply) -> None:
    reply(error_log_text())
