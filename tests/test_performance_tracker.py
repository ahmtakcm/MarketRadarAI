import builtins
import importlib
import sys

from core import performance_tracker


def test_performance_tracker_imports_without_settings_file(monkeypatch):
    original_import = builtins.__import__
    sys.modules.pop("core.performance_tracker", None)

    def guarded_import(name, *args, **kwargs):
        if name == "config":
            raise FileNotFoundError("settings.json missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    module = importlib.import_module("core.performance_tracker")

    assert module.SIGNAL_HORIZONS_BARS == [1, 3, 5]
    assert module.PERFORMANCE_LOG_PATH.name == "performance_log.jsonl"


def _pending(signal="LONG", *, stop_loss=95.0, take_profit_levels=None):
    return {
        "timestamp": 99,
        "id": f"BTCUSDT_15m_FIBB_STRATEGY_1000_{signal}",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "strategy": "FIBB_STRATEGY",
        "signal": signal,
        "reason": "breakout",
        "entry_price": 100.0,
        "stop_loss": stop_loss,
        "take_profit_levels": take_profit_levels or [105.0, 110.0],
        "close_time": 1000,
        "target_horizons": [1, 2],
    }


def test_register_signal_stores_trade_plan_levels(monkeypatch):
    monkeypatch.setattr(performance_tracker, "SIGNAL_HORIZONS_BARS", [1, 2])
    state = {}
    levels = {"close": 100.0, "close_time": 1000}

    performance_tracker.register_signal(
        state,
        "BTCUSDT",
        "15m",
        "FIBB_STRATEGY",
        "LONG",
        "breakout",
        levels,
        stop_loss=95.0,
        take_profit_levels=[105.0, 110.0],
    )

    assert state["pending_signals"][0]["stop_loss"] == 95.0
    assert state["pending_signals"][0]["take_profit_levels"] == [105.0, 110.0]


def test_finalize_pending_signals_records_long_tp_hit(monkeypatch):
    rows = []
    state = {"pending_signals": [_pending("LONG")]}
    candles = [
        {"close_time": 1000, "close": 100.0, "high": 101.0, "low": 99.0},
        {"close_time": 2000, "close": 104.0, "high": 104.5, "low": 99.5},
        {"close_time": 3000, "close": 106.0, "high": 106.5, "low": 102.0},
    ]

    monkeypatch.setattr(performance_tracker, "append_jsonl", lambda _path, row: rows.append(row))

    performance_tracker.finalize_pending_signals(
        state,
        lambda _symbol, _timeframe, _limit: candles,
        lambda _timeframe: len(candles),
    )

    assert state["pending_signals"] == []
    assert rows[0]["tp_sl_outcome"] == {
        "status": "TP_HIT",
        "bar_offset": 2,
        "close_time": 3000,
        "take_profit": 105.0,
        "tp_index": 1,
    }
    assert rows[0]["outcomes"]["2_bar"]["pnl_pct"] == 6.0


def test_finalize_pending_signals_records_short_sl_hit(monkeypatch):
    rows = []
    state = {"pending_signals": [_pending("SHORT", stop_loss=105.0, take_profit_levels=[95.0, 90.0])]}
    candles = [
        {"close_time": 1000, "close": 100.0, "high": 101.0, "low": 99.0},
        {"close_time": 2000, "close": 103.0, "high": 106.0, "low": 98.0},
        {"close_time": 3000, "close": 102.0, "high": 104.0, "low": 96.0},
    ]

    monkeypatch.setattr(performance_tracker, "append_jsonl", lambda _path, row: rows.append(row))

    performance_tracker.finalize_pending_signals(
        state,
        lambda _symbol, _timeframe, _limit: candles,
        lambda _timeframe: len(candles),
    )

    assert state["pending_signals"] == []
    assert rows[0]["tp_sl_outcome"] == {
        "status": "SL_HIT",
        "bar_offset": 1,
        "close_time": 2000,
        "stop_loss": 105.0,
    }
