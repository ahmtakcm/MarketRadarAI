import telegram_commands
from telegram import handlers, messages


class _FakeTelegramResponse:
    def json(self):
        return {"ok": True, "result": []}


def test_active_dispatcher_group_commands_remain_disabled():
    assert telegram_commands.GROUP_SAFE_COMMANDS == set()


def test_active_dispatcher_admin_command_set_is_stable():
    assert telegram_commands.ADMIN_PRIVATE_COMMANDS == {
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


def test_polling_does_not_own_command_menu_sync(monkeypatch):
    sync_calls = []

    monkeypatch.setattr(telegram_commands, "sync_telegram_commands", lambda: sync_calls.append("sync"))
    monkeypatch.setattr(telegram_commands.requests, "get", lambda *_args, **_kwargs: _FakeTelegramResponse())

    telegram_commands.poll_telegram_commands(lambda _text: None)

    assert sync_calls == []


def test_scan_now_sets_force_scan_flag_without_changing_modes(monkeypatch):
    cfg = {"runtime": {}, "modes": {"scalp": True, "intraday": True, "midterm": True}}
    saved = {}
    replies = []

    def fake_update_config(mutator):
        mutator(cfg)
        saved.update(cfg)
        return cfg

    monkeypatch.setattr(handlers, "load_config", lambda: cfg)
    monkeypatch.setattr(handlers, "update_config", fake_update_config)
    monkeypatch.setattr(handlers, "send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/scan_now"},
        lambda _text: None,
    )

    assert saved["runtime"]["force_scan_once"] is True
    assert saved["modes"]["scalp"] is True
    assert replies == [
        "Anlik tarama tetiklendi. Aktif modlar icin mum kapanisi beklenmeden tarama baslatiliyor."
    ]


def test_help_uses_marketradarai_identity(monkeypatch):
    replies = []

    monkeypatch.setattr(handlers, "load_config", lambda: {"runtime": {}})
    monkeypatch.setattr(handlers, "send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/help"},
        lambda _text: None,
    )

    assert replies
    assert replies[0].startswith("MarketRadarAI HELP")
    assert "Durum ve loglar" in replies[0]
    assert "Watchlist" in replies[0]
    assert "admin private" in replies[0]
    assert "/watchlist" in replies[0]
    for command in telegram_commands.ADMIN_PRIVATE_COMMANDS:
        assert command in replies[0]


def test_status_includes_modes_watchlist_runtime_and_health(monkeypatch):
    cfg = {
        "modes": {"scalp": True, "intraday": True, "midterm": False},
        "filters": {"fake_breakout_filter": True, "volume_confirmation": False},
        "limits": {"cooldown_minutes": 30},
        "watchlist": {"symbols": ["BTCUSDT", "TSLAUSDT", "UNKNOWNUSDT"]},
        "runtime": {},
    }
    replies = []

    monkeypatch.setattr(handlers, "load_config", lambda: cfg)
    monkeypatch.setattr(messages, "load_config", lambda: cfg)
    monkeypatch.setattr(messages, "get_valid_futures_symbols", lambda: ["BTCUSDT", "TESLAUSDT"])
    monkeypatch.setattr(messages, "get_config_path", lambda: messages.BASE_DIR / "runtime" / "remote_config.json")
    monkeypatch.setattr(handlers, "send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/status"},
        lambda _text: None,
    )

    assert replies
    assert replies[0].startswith("MarketRadarAI STATUS")
    assert "SAGLIK" in replies[0]
    assert "config: runtime\\remote_config.json" in replies[0] or "config: runtime/remote_config.json" in replies[0]
    assert "Aktif calisan: scalp, intraday" in replies[0]
    assert "Watchlist: 3 kayit | supported 2 | unsupported 1" in replies[0]


def test_watchlist_shows_supported_and_unsupported_symbols(monkeypatch):
    cfg = {
        "watchlist": {"symbols": ["BTCUSDT", "ETHUSDT", "AAPLUSDT", "XAUUSDT"]},
        "runtime": {},
    }
    replies = []

    monkeypatch.setattr(handlers, "load_config", lambda: cfg)
    monkeypatch.setattr(messages, "get_valid_futures_symbols", lambda: ["BTCUSDT", "ETHUSDT"])
    monkeypatch.setattr(handlers, "send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/watchlist"},
        lambda _text: None,
    )

    assert replies
    assert "MarketRadarAI WATCHLIST" in replies[0]
    assert "Summary: MEXC | requested 4 | supported 2 | unsupported 2" in replies[0]
    assert "Supported scan symbols:" in replies[0]
    assert "Unsupported symbols:" in replies[0]
    assert "AAPLUSDT, XAUUSDT" in replies[0]


def test_add_symbol_accepts_resolved_alias_symbol(monkeypatch):
    cfg = {"watchlist": {"symbols": []}, "runtime": {}}
    saved = {}
    replies = []

    def fake_update_config(mutator):
        mutator(cfg)
        saved.update(cfg)
        return cfg

    monkeypatch.setattr(handlers, "load_config", lambda: cfg)
    monkeypatch.setattr(handlers, "update_config", fake_update_config)
    monkeypatch.setattr(handlers, "get_valid_futures_symbols", lambda: ["TESLAUSDT"])
    monkeypatch.setattr(handlers, "send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/add_symbol TSLAUSDT"},
        lambda _text: None,
    )

    assert saved["watchlist"]["symbols"] == ["TESLAUSDT"]
    assert replies
    assert "TESLAUSDT" in replies[0]
    assert "TSLAUSDT" in replies[0]


def test_add_symbol_rejects_unknown_symbol_after_resolution(monkeypatch):
    cfg = {"watchlist": {"symbols": []}, "runtime": {}}
    saved = {}
    replies = []

    def fake_update_config(mutator):
        mutator(cfg)
        saved.update(cfg)
        return cfg

    monkeypatch.setattr(handlers, "load_config", lambda: cfg)
    monkeypatch.setattr(handlers, "update_config", fake_update_config)
    monkeypatch.setattr(handlers, "get_valid_futures_symbols", lambda: ["BTCUSDT"])
    monkeypatch.setattr(handlers, "send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/add_symbol UNKNOWNUSDT"},
        lambda _text: None,
    )

    assert saved == {}
    assert replies
    assert "UNKNOWNUSDT" in replies[0]


def test_watchlist_shows_resolved_alias_symbols(monkeypatch):
    cfg = {
        "watchlist": {"symbols": ["TSLAUSDT", "SP500USDT", "UNKNOWNUSDT"]},
        "runtime": {},
    }
    replies = []

    monkeypatch.setattr(handlers, "load_config", lambda: cfg)
    monkeypatch.setattr(
        messages,
        "get_valid_futures_symbols",
        lambda: ["TESLAUSDT", "SPX500USDT"],
    )
    monkeypatch.setattr(handlers, "send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/watchlist"},
        lambda _text: None,
    )

    assert replies
    assert "Resolved aliases:" in replies[0]
    assert "TSLAUSDT -> TESLAUSDT" in replies[0]
    assert "SP500USDT -> SPX500USDT" in replies[0]
    assert "UNKNOWNUSDT" in replies[0]
