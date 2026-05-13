from __future__ import annotations

import os


def resolve_log_level() -> str:
    return os.getenv("MARKETRADAR_LOG_LEVEL", os.getenv("MEXC_LOG_LEVEL", "INFO")).upper()
