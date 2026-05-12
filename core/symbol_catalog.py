from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CATALOG_CACHE: dict[str, Any] | None = None
_CATALOG_PATH = Path("data/symbol_catalog.json")


def load_catalog(force_reload: bool = False) -> dict[str, Any]:
    global _CATALOG_CACHE

    if _CATALOG_CACHE is not None and not force_reload:
        return _CATALOG_CACHE

    try:
        if _CATALOG_PATH.exists():
            _CATALOG_CACHE = json.loads(
                _CATALOG_PATH.read_text(encoding="utf-8")
            )
        else:
            _CATALOG_CACHE = {}
    except Exception:
        _CATALOG_CACHE = {}

    return _CATALOG_CACHE


def get_symbol_metadata(symbol: str) -> dict[str, Any] | None:
    catalog = load_catalog()
    return catalog.get(symbol.upper().strip())
