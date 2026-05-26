from core import scanner


def _plan():
    return {
        "mode": "intraday",
        "label": "Gün İçi",
        "bias": "4h",
        "setup": "1h",
        "entry": "15m",
    }


def _levels():
    return {
        "close_time": 123,
        "close": 100.0,
        "center": 99.0,
        "upper_fib1": 105.0,
        "upper_fib2": 110.0,
        "upper_fib3": 116.18,
        "upper_fib4": 126.18,
        "upper_fib5": 136.18,
        "lower_fib1": 95.0,
        "lower_fib2": 90.0,
        "lower_fib3": 83.82,
        "lower_fib4": 73.82,
        "lower_fib5": 63.82,
    }


def test_scanner_renders_phase_only_without_trade_side_effects(monkeypatch):
    registered = []
    logged = []

    monkeypatch.setattr(scanner, "_active_mode_plans", lambda: [_plan()])
    monkeypatch.setattr(scanner, "load_config", lambda: {"filters": {}})
    monkeypatch.setattr(scanner, "_fetch_context", lambda *_args: ([], _levels()))
    monkeypatch.setattr(
        scanner,
        "_generate_signals",
        lambda _context: [{
            "strategy": "FIBB_STRATEGY",
            "strategy_key": "fibb_strategy",
            "candidate_type": "phase",
            "signal": "EXTREME_OVERSOLD",
            "reason": "Fib4-5 altı",
            "quality": "WATCH",
        }],
    )
    monkeypatch.setattr(scanner, "log_signal", lambda *args, **kwargs: logged.append(args))
    monkeypatch.setattr(scanner, "_register_signal", lambda *args, **kwargs: registered.append(args))

    lines = scanner.build_signal_lines(["BTCUSDT"], {"last_processed_close_times": {}})

    assert "EXTREME_OVERSOLD | WATCH" in lines[0]
    assert "Entry:" not in lines[0]
    assert logged == []
    assert registered == []


def test_scanner_uses_strategy_stop_loss_when_present(monkeypatch):
    registered = []

    monkeypatch.setattr(scanner, "_active_mode_plans", lambda: [_plan()])
    monkeypatch.setattr(scanner, "load_config", lambda: {"filters": {}})
    monkeypatch.setattr(scanner, "_fetch_context", lambda *_args: ([], _levels()))
    monkeypatch.setattr(
        scanner,
        "_generate_signals",
        lambda _context: [{
            "strategy": "FIBB_STRATEGY",
            "strategy_key": "fibb_strategy",
            "candidate_type": "trade",
            "signal": "LONG",
            "reason": "TREND_EXPANSION\nFib pullback\nEMA34 geri dönüş",
            "quality": "HIGH",
            "score": 65,
            "stop_loss": 83.82,
        }],
    )
    monkeypatch.setattr(
        scanner,
        "analyze_mtf_signal",
        lambda *_args: {"allowed": True, "quality": "LOW", "score": 10},
    )
    monkeypatch.setattr(scanner, "macro_direction_for_symbol", lambda _symbol: None)
    monkeypatch.setattr(scanner, "get_macro_signal", lambda: {})
    monkeypatch.setattr(scanner, "log_signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(scanner, "_register_signal", lambda *args, **kwargs: registered.append(args))

    lines = scanner.build_signal_lines(["BTCUSDT"], {"last_processed_close_times": {}})

    assert "LONG | HIGH 65/100" in lines[0]
    assert "SL: 83.82" in lines[0]
    assert registered
