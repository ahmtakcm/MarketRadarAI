import json
import shutil
import uuid
from pathlib import Path

from core import state_store


def _case_dir():
    path = Path("tests") / "_tmp_runtime_tests" / uuid.uuid4().hex
    path.mkdir(parents=True)
    return path.resolve()


def test_state_store_loads_legacy_state_with_schema_version():
    case_dir = _case_dir()
    path = case_dir / "state.json"
    path.write_text(json.dumps({"last_sent_message": "hello"}), encoding="utf-8")

    try:
        state = state_store.load_state(path=path)

        assert state["schema_version"] == state_store.STATE_SCHEMA_VERSION
        assert state["last_sent_message"] == "hello"
        assert state["pending_signals"] == []
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_state_store_recovers_from_corrupt_file():
    case_dir = _case_dir()
    path = case_dir / "state.json"
    path.write_text("{not-json", encoding="utf-8")

    try:
        state = state_store.load_state(path=path)

        assert state["schema_version"] == state_store.STATE_SCHEMA_VERSION
        assert state["pending_signals"] == []
        assert path.exists()
        assert path.with_name(path.name + ".broken").exists()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_state_store_save_is_atomic():
    case_dir = _case_dir()
    path = case_dir / "state.json"

    try:
        state_store.save_state({"pending_signals": [{"id": "abc"}]}, path=path)
        saved = json.loads(path.read_text(encoding="utf-8"))

        assert saved["schema_version"] == state_store.STATE_SCHEMA_VERSION
        assert saved["pending_signals"] == [{"id": "abc"}]
        if path.with_suffix(".tmp").exists():
            assert json.loads(path.with_suffix(".tmp").read_text(encoding="utf-8")) == saved
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
