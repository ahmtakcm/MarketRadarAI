import json
import os

from config import STATE_FILE_PATH

DEFAULT_STATE = {
    "last_sent_message": None,
    "daily_commentary": {},
    "last_processed_close_times": {},
    "pending_signals": []
}


def load_state():
    if not os.path.exists(STATE_FILE_PATH):
        return DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULT_STATE.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULT_STATE.copy()


def save_state(state):
    with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
