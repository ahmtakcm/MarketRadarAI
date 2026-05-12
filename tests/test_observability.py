from pathlib import Path

from core.observability import (
    build_scan_observation,
    build_startup_metadata,
    format_scan_observation,
    format_startup_metadata,
)
from single_instance import SingleInstance


def test_startup_metadata_includes_runtime_paths():
    cfg = {
        "modes": {"scalp": True, "intraday": True, "midterm": False},
        "watchlist": {"symbols": ["BTCUSDT", "ETHUSDT"]},
    }

    metadata = build_startup_metadata(
        cfg,
        ["scalp", "intraday"],
        state_path=Path("data/state.json"),
        runtime_config_path=Path("runtime/remote_config.json"),
    )
    text = format_startup_metadata(metadata)

    assert metadata["exchange"] == "MEXC"
    assert metadata["active_modes"] == "scalp,intraday"
    assert metadata["watchlist_count"] == 2
    assert "MarketRadarAI startup" in text
    assert "runtime" in text
    assert "remote_config.json" in text


def test_scan_observation_format_includes_modes_and_symbol_count():
    observation = build_scan_observation(["intraday", "midterm"], ["BTCUSDT", "ETHUSDT"])

    assert observation == {"active_modes": "intraday,midterm", "symbol_count": 2}
    assert format_scan_observation("start", observation) == (
        "MarketRadarAI scan start | active_modes=intraday,midterm | symbol_count=2"
    )


def test_deployment_docs_include_current_service_and_restart_loop_triage():
    text = Path("docs/DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "mexc-tarama-bot.service" in text
    assert "MarketRadarAI scanner service" in text
    assert "Restart Loop Triage" in text
    assert "Restart=on-failure" in text
    assert "StandardError=journal" in text
    assert "journalctl -u mexc-tarama-bot.service" in text


def test_duplicate_instance_exit_is_visible(caplog, capsys):
    lock_path = Path("storage/alarm_bot.lock")
    guard = SingleInstance("MarketRadarAI", lock_path)

    with caplog.at_level("WARNING"):
        guard._exit_existing_instance()

    assert "MarketRadarAI zaten calisiyor" in caplog.text
    assert str(lock_path) in caplog.text
    assert "Yeni kopya baslatilmadi" in capsys.readouterr().out
