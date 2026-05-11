import json
import os
from pathlib import Path

try:
    from config import STATE_FILE_PATH
except Exception:
    STATE_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "state.json"

STATE_SCHEMA_VERSION = 1

DEFAULT_STATE = {
    "schema_version": STATE_SCHEMA_VERSION,
    "last_sent_message": None,
    "daily_commentary": {},
    "last_processed_close_times": {},
    "pending_signals": []
}


def migrate_state(state):
    migrated = DEFAULT_STATE.copy()
    if isinstance(state, dict):
        migrated.update(state)
    migrated["schema_version"] = STATE_SCHEMA_VERSION
    return migrated


def _broken_path(path):
    path = Path(path)
    return path.with_name(path.name + ".broken")


def _archive_broken(path):
    path = Path(path)
    try:
        path.replace(_broken_path(path))
    except PermissionError:
        _broken_path(path).write_bytes(path.read_bytes())


def _replace_file(tmp, target):
    try:
        os.replace(tmp, target)
    except PermissionError:
        try:
            os.rename(tmp, target)
        except PermissionError:
            target.write_bytes(tmp.read_bytes())
            try:
                tmp.unlink(missing_ok=True)
            except PermissionError:
                pass


def load_state(path=None):
    path = Path(path or STATE_FILE_PATH)
    if not path.exists():
        return migrate_state({})

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return migrate_state(data)
    except Exception:
        try:
            _archive_broken(path)
        except Exception:
            pass
        default = migrate_state({})
        save_state(default, path=path)
        return default


def save_state(state, path=None):
    path = Path(path or STATE_FILE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(migrate_state(state), f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    _replace_file(tmp, path)


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
