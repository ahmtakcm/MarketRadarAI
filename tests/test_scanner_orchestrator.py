import builtins
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import scanner_orchestrator
from core.scanner_orchestrator import ScannerRuntime


class FakeMarketDataService:
    def __init__(self):
        self.fetch_calls = []

    def fetch_klines(self, symbol, interval, limit):
        self.fetch_calls.append((symbol, interval, limit))
        return []

    def get_kline_limit(self, interval):
        return 5

    def get_valid_futures_symbols(self):
        return ["BTCUSDT", "TESLAUSDT"]


def _runtime():
    return ScannerRuntime(
        send_telegram=lambda _text: None,
        poll_telegram_commands=lambda _send: None,
    )


def test_orchestrator_syncs_telegram_menu_once_before_polling_thread():
    calls = []
    runtime = ScannerRuntime(
        send_telegram=lambda _text: None,
        poll_telegram_commands=lambda _send: None,
        sync_telegram_commands=lambda: calls.append("sync"),
    )

    runtime.sync_telegram_menu_once()
    runtime.sync_telegram_menu_once()

    assert calls == ["sync"]


def test_orchestrator_requested_symbols_falls_back_without_config(monkeypatch):
    original_import = builtins.__import__
    sys.modules.pop("config", None)

    def guarded_import(name, *args, **kwargs):
        if name == "config":
            raise FileNotFoundError("settings.json missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert scanner_orchestrator.get_requested_symbols() == []


def test_scanner_import_with_injected_market_data_service_does_not_require_settings(monkeypatch):
    original_import = builtins.__import__
    sys.modules.pop("config", None)
    sys.modules.pop("core.scanner", None)

    def guarded_import(name, *args, **kwargs):
        if name == "config":
            raise FileNotFoundError("settings.json missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    scanner = importlib.import_module("core.scanner")

    assert scanner.get_active_symbols(FakeMarketDataService()) == ["BTCUSDT", "TESLAUSDT"]


def test_orchestrator_watchlist_filter_keeps_supported_and_logs_unsupported(monkeypatch, caplog):
    monkeypatch.setattr(
        scanner_orchestrator,
        "load_config",
        lambda: {"watchlist": {"symbols": ["BTCUSDT", "ETHUSDT", "AAPLUSDT"]}},
    )

    with caplog.at_level("INFO"):
        selected = _runtime().apply_watchlist_filter(["BTCUSDT", "ETHUSDT"])

    assert selected == ["BTCUSDT", "ETHUSDT"]
    assert "MarketRadarAI asset universe | exchange=MEXC | requested=3 | supported=2 | unsupported=1" in caplog.text
    assert "AAPLUSDT" in caplog.text


def test_orchestrator_force_scan_consume_clears_flag_and_preserves_modes(monkeypatch):
    cfg = {
        "runtime": {"force_scan_once": True},
        "modes": {"scalp": True, "intraday": True, "midterm": False},
        "watchlist": {"symbols": ["BTCUSDT", "ETHUSDT"]},
    }
    saved = {}

    def fake_update_config(mutator):
        mutator(cfg)
        saved.update(cfg)
        return cfg

    monkeypatch.setattr(scanner_orchestrator, "update_config", fake_update_config)

    assert _runtime().consume_force_scan_request() is True
    assert saved["runtime"]["force_scan_once"] is False
    assert saved["modes"] == {"scalp": True, "intraday": True, "midterm": False}


def test_orchestrator_scan_cycle_isolates_duplicate_signal_delivery(monkeypatch):
    sent = []
    saved_states = []
    state = {"last_sent_message": "existing"}

    monkeypatch.setattr(scanner_orchestrator, "load_config", lambda: {"modes": {"scalp": True}})
    monkeypatch.setattr(scanner_orchestrator, "build_signal_message", lambda _symbols, _state, _service: "existing")
    monkeypatch.setattr(scanner_orchestrator, "get_daily_commentaries", lambda _symbols, _state, _service: [])
    monkeypatch.setattr(scanner_orchestrator, "finalize_pending_signals", lambda *_args: None)
    monkeypatch.setattr(scanner_orchestrator, "save_state", lambda value: saved_states.append(dict(value)))

    runtime = ScannerRuntime(
        send_telegram=lambda text: sent.append(text),
        poll_telegram_commands=lambda _send: None,
    )
    runtime.run_scan_cycle(state, ["BTCUSDT"])

    assert sent == []
    assert saved_states == [{"last_sent_message": "existing"}]


def test_orchestrator_uses_injected_market_data_service_for_symbol_discovery():
    service = FakeMarketDataService()
    runtime = ScannerRuntime(
        send_telegram=lambda _text: None,
        poll_telegram_commands=lambda _send: None,
        market_data_service=service,
    )

    assert runtime._fetch_live_symbols_once() == ["BTCUSDT", "TESLAUSDT"]


def test_unknown_symbol_does_not_reach_market_data_service(monkeypatch):
    service = FakeMarketDataService()
    runtime = ScannerRuntime(
        send_telegram=lambda _text: None,
        poll_telegram_commands=lambda _send: None,
        market_data_service=service,
    )

    monkeypatch.setattr(
        scanner_orchestrator,
        "load_config",
        lambda: {"watchlist": {"symbols": ["UNKNOWNUSDT"]}, "modes": {"scalp": True}},
    )
    monkeypatch.setattr(scanner_orchestrator, "build_signal_message", lambda _symbols, _state, _service: None)
    monkeypatch.setattr(scanner_orchestrator, "get_daily_commentaries", lambda _symbols, _state, _service: [])
    monkeypatch.setattr(scanner_orchestrator, "finalize_pending_signals", lambda *_args: None)
    monkeypatch.setattr(scanner_orchestrator, "save_state", lambda _state: None)

    symbols = runtime.apply_watchlist_filter(["BTCUSDT", "TESLAUSDT"])
    runtime.run_scan_cycle({"last_sent_message": None}, symbols)

    assert symbols == []
    assert service.fetch_calls == []
