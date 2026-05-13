import runtime_env
from telegram import settings


def test_marketradar_log_level_takes_precedence(monkeypatch):
    monkeypatch.setenv("MARKETRADAR_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MEXC_LOG_LEVEL", "ERROR")

    assert runtime_env.resolve_log_level() == "DEBUG"


def test_legacy_mexc_log_level_still_works(monkeypatch):
    monkeypatch.delenv("MARKETRADAR_LOG_LEVEL", raising=False)
    monkeypatch.setenv("MEXC_LOG_LEVEL", "WARNING")

    assert runtime_env.resolve_log_level() == "WARNING"


def test_telegram_chat_ids_can_be_overridden_by_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "111")
    monkeypatch.setenv("TELEGRAM_GROUP_CHAT_ID", "-222")

    admin_chat_id, group_chat_id, _allowed_chat_id = settings.resolve_chat_ids()

    assert admin_chat_id == "111"
    assert group_chat_id == "-222"
