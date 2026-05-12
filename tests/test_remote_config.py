import json
import shutil
import threading
import uuid
from pathlib import Path

import remote_config


def _case_dir():
    path = Path("tests") / "_tmp_runtime_tests" / uuid.uuid4().hex
    path.mkdir(parents=True)
    return path.resolve()


def test_runtime_config_migrates_legacy_without_losing_overrides(monkeypatch):
    case_dir = _case_dir()
    legacy_path = case_dir / "remote_config.json"
    runtime_path = case_dir / "runtime" / "remote_config.json"
    legacy_path.write_text(
        json.dumps({"modes": {"scalp": True}, "runtime": {"force_scan_once": True}}),
        encoding="utf-8",
    )

    try:
        monkeypatch.setattr(remote_config, "LEGACY_CONFIG_PATH", legacy_path)
        monkeypatch.setattr(remote_config, "CONFIG_PATH", runtime_path)

        cfg = remote_config.load_config()

        assert cfg["schema_version"] == remote_config.SCHEMA_VERSION
        assert cfg["modes"]["scalp"] is True
        assert cfg["runtime"]["force_scan_once"] is True
        assert runtime_path.exists()
        assert json.loads(legacy_path.read_text(encoding="utf-8"))["modes"]["scalp"] is True
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_runtime_config_recovers_from_corrupt_file(monkeypatch):
    case_dir = _case_dir()
    legacy_path = case_dir / "remote_config.json"
    runtime_path = case_dir / "runtime" / "remote_config.json"
    runtime_path.parent.mkdir()
    runtime_path.write_text("{not-json", encoding="utf-8")

    try:
        monkeypatch.setattr(remote_config, "LEGACY_CONFIG_PATH", legacy_path)
        monkeypatch.setattr(remote_config, "CONFIG_PATH", runtime_path)

        cfg = remote_config.load_config()

        assert cfg["schema_version"] == remote_config.SCHEMA_VERSION
        assert cfg["modes"]["intraday"] is True
        assert runtime_path.exists()
        assert runtime_path.with_name(runtime_path.name + ".broken").exists()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_runtime_config_save_is_atomic_and_backward_compatible(monkeypatch):
    case_dir = _case_dir()
    runtime_path = case_dir / "runtime" / "remote_config.json"

    try:
        monkeypatch.setattr(remote_config, "CONFIG_PATH", runtime_path)

        remote_config.save_config({"modes": {"scalp": True}})
        saved = json.loads(runtime_path.read_text(encoding="utf-8"))

        assert saved["schema_version"] == remote_config.SCHEMA_VERSION
        assert saved["modes"]["scalp"] is True
        assert saved["modes"]["intraday"] is True
        if runtime_path.with_suffix(".tmp").exists():
            assert json.loads(runtime_path.with_suffix(".tmp").read_text(encoding="utf-8")) == saved
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_runtime_config_update_lock_preserves_concurrent_changes(monkeypatch):
    case_dir = _case_dir()
    runtime_path = case_dir / "runtime" / "remote_config.json"

    first_mutator_entered = threading.Event()
    release_first_mutator = threading.Event()

    try:
        monkeypatch.setattr(remote_config, "CONFIG_PATH", runtime_path)
        remote_config.save_config({
            "modes": {"scalp": False},
            "watchlist": {"symbols": ["BTCUSDT"]},
        })

        def enable_scalp(cfg):
            first_mutator_entered.set()
            assert release_first_mutator.wait(timeout=2)
            cfg.setdefault("modes", {})["scalp"] = True

        def add_symbol(cfg):
            cfg.setdefault("watchlist", {}).setdefault("symbols", []).append("ETHUSDT")

        first = threading.Thread(target=lambda: remote_config.update_config(enable_scalp))
        second = threading.Thread(target=lambda: remote_config.update_config(add_symbol))

        first.start()
        assert first_mutator_entered.wait(timeout=2)
        second.start()
        release_first_mutator.set()
        first.join(timeout=2)
        second.join(timeout=2)

        assert not first.is_alive()
        assert not second.is_alive()

        saved = remote_config.load_config()
        assert saved["modes"]["scalp"] is True
        assert saved["watchlist"]["symbols"] == ["BTCUSDT", "ETHUSDT"]
    finally:
        release_first_mutator.set()
        shutil.rmtree(case_dir, ignore_errors=True)
