import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import scanner_orchestrator
from core.scanner_orchestrator import ScannerRuntime


def _runtime():
    return ScannerRuntime(
        send_telegram=lambda _text: None,
        poll_telegram_commands=lambda _send: None,
    )


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

    monkeypatch.setattr(scanner_orchestrator, "load_config", lambda: cfg)
    monkeypatch.setattr(scanner_orchestrator, "save_config", lambda value: saved.update(value))

    assert _runtime().consume_force_scan_request() is True
    assert saved["runtime"]["force_scan_once"] is False
    assert saved["modes"] == {"scalp": True, "intraday": True, "midterm": False}


def test_orchestrator_scan_cycle_isolates_duplicate_signal_delivery(monkeypatch):
    sent = []
    saved_states = []
    state = {"last_sent_message": "existing"}

    monkeypatch.setattr(scanner_orchestrator, "load_config", lambda: {"modes": {"scalp": True}})
    monkeypatch.setattr(scanner_orchestrator, "build_signal_message", lambda _symbols, _state: "existing")
    monkeypatch.setattr(scanner_orchestrator, "get_daily_commentaries", lambda _symbols, _state: [])
    monkeypatch.setattr(scanner_orchestrator, "finalize_pending_signals", lambda *_args: None)
    monkeypatch.setattr(scanner_orchestrator, "save_state", lambda value: saved_states.append(dict(value)))

    runtime = ScannerRuntime(
        send_telegram=lambda text: sent.append(text),
        poll_telegram_commands=lambda _send: None,
    )
    runtime.run_scan_cycle(state, ["BTCUSDT"])

    assert sent == []
    assert saved_states == [{"last_sent_message": "existing"}]
