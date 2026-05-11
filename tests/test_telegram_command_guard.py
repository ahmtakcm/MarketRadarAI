import telegram_commands


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


def test_scan_now_sets_force_scan_flag_without_changing_modes(monkeypatch):
    cfg = {"runtime": {}, "modes": {"scalp": True, "intraday": True, "midterm": True}}
    saved = {}
    replies = []

    monkeypatch.setattr(telegram_commands, "load_config", lambda: cfg)
    monkeypatch.setattr(telegram_commands, "save_config", lambda value: saved.update(value))
    monkeypatch.setattr(telegram_commands, "_send_to_chat", lambda _chat_id, text: replies.append(text))

    telegram_commands.handle_command_message(
        {"chat": {"id": telegram_commands.ADMIN_CHAT_ID}, "text": "/scan_now"},
        lambda _text: None,
    )

    assert saved["runtime"]["force_scan_once"] is True
    assert saved["modes"]["scalp"] is True
    assert replies == [
        "Anlik tarama tetiklendi. Aktif modlar icin mum kapanisi beklenmeden tarama baslatiliyor."
    ]
