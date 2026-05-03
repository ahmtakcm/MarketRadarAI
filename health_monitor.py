from __future__ import annotations

import os
import time
from pathlib import Path

START_TIME = time.time()
BASE_DIR = Path(__file__).resolve().parent


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}s {m}dk {s}sn"
    if m:
        return f"{m}dk {s}sn"
    return f"{s}sn"


def build_health_text() -> str:
    uptime = format_duration(time.time() - START_TIME)

    app_log = BASE_DIR / "logs" / "app.log"
    boot_log = BASE_DIR / "logs" / "boot.out"
    state_file = BASE_DIR / "data" / "state.json"

    def info(path: Path) -> str:
        if not path.exists():
            return "yok"
        age = format_duration(time.time() - path.stat().st_mtime)
        size_kb = path.stat().st_size / 1024
        return f"var | {size_kb:.1f} KB | son değişim {age} önce"

    return (
        "🩺 SİSTEM SAĞLIĞI\n\n"
        f"Uptime: {uptime}\n"
        f"PID: {os.getpid()}\n"
        f"Çalışma klasörü: {BASE_DIR}\n\n"
        f"app.log: {info(app_log)}\n"
        f"boot.out: {info(boot_log)}\n"
        f"state.json: {info(state_file)}"
    )
