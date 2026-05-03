import logging
import time
from typing import Any, Dict, List, Optional

import requests

MEXC_BASE = "https://contract.mexc.com"

INTERVAL_MAP = {
    "1m": "Min1",
    "3m": "Min5",      # MEXC futures tarafinda Min3 yok; guvenli fallback
    "5m": "Min5",
    "15m": "Min15",
    "30m": "Min30",
    "1h": "Min60",
    "4h": "Hour4",
    "1d": "Day1",
    "1w": "Week1",
}

SECONDS_MAP = {
    "Min1": 60,
    "Min5": 300,
    "Min15": 900,
    "Min30": 1800,
    "Min60": 3600,
    "Hour4": 14400,
    "Day1": 86400,
    "Week1": 604800,
}

_session = requests.Session()


def _get(path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
    url = f"{MEXC_BASE}{path}"
    try:
        response = _session.get(url, params=params or {}, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return {"success": False, "data": None, "message": "non-dict response"}
        return data
    except Exception as exc:
        logging.warning("MEXC GET hata | path=%s params=%s err=%s", path, params, exc)
        return {"success": False, "data": None, "message": str(exc)}


def normalize_symbol(symbol: str) -> str:
    s = str(symbol or "").upper().strip()
    s = s.replace("-", "_").replace("/", "_")

    if "_" in s:
        return s

    if s.endswith("USDT"):
        return s[:-4] + "_USDT"

    return s


def denormalize_symbol(symbol: str) -> str:
    return str(symbol or "").upper().replace("_", "")


def get_symbols() -> List[str]:
    data = _get("/api/v1/contract/detail")
    rows = data.get("data") if data.get("success") else None

    if not isinstance(rows, list):
        logging.warning("MEXC sembol listesi alinamadi")
        return []

    symbols: List[str] = []
    for item in rows:
        if not isinstance(item, dict):
            continue

        symbol = item.get("symbol")
        quote = item.get("quoteCoin")
        state = item.get("state")

        if not symbol:
            continue

        if quote and str(quote).upper() != "USDT":
            continue

        if state is not None and str(state) not in ("0", "1"):
            continue

        symbols.append(denormalize_symbol(symbol))

    return sorted(set(symbols))


def get_ticker(symbol: str) -> Dict[str, Any]:
    mexc_symbol = normalize_symbol(symbol)
    data = _get("/api/v1/contract/ticker", {"symbol": mexc_symbol})
    payload = data.get("data") if data.get("success") else None

    if isinstance(payload, dict):
        return payload

    if isinstance(payload, list) and payload:
        return payload[0]

    return {}


def _ticker_sort_value(item: Dict[str, Any]) -> float:
    for key in ("amount24", "volume24", "volume", "vol", "holdVol"):
        try:
            value = item.get(key)
            if value is not None:
                return float(value)
        except Exception:
            continue
    return 0.0


def get_ranked_futures_symbols(limit: int = 20, min_24h_volume: float = 0) -> List[str]:
    data = _get("/api/v1/contract/ticker")
    payload = data.get("data") if data.get("success") else None

    if not isinstance(payload, list):
        return get_symbols()[:max(int(limit), 0)]

    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        symbol = denormalize_symbol(item.get("symbol"))
        if not symbol.endswith("USDT"):
            continue

        sort_value = _ticker_sort_value(item)
        if sort_value < float(min_24h_volume or 0):
            continue

        rows.append((symbol, sort_value))

    rows.sort(key=lambda row: row[1], reverse=True)

    ranked = []
    seen = set()
    for symbol, _value in rows:
        if symbol not in seen:
            ranked.append(symbol)
            seen.add(symbol)

    return ranked[:max(int(limit), 0)]


def validate_futures_symbol(symbol: str, tf: str = "15m", min_candles: int = 30):
    normalized = normalize_symbol(symbol)
    plain_symbol = denormalize_symbol(normalized)

    if not plain_symbol.endswith("USDT"):
        return False, "only USDT futures symbols are supported"

    ticker = get_ticker(plain_symbol)
    if not ticker:
        return False, "ticker not found"

    candles = fetch_klines(plain_symbol, tf, min_candles)
    if len(candles) < int(min_candles):
        return False, f"not enough candles: {len(candles)}/{min_candles}"

    return True, "ok"


def get_klines(symbol: str, interval: str = "15m", limit: int = 200) -> List[Dict[str, float]]:
    mexc_symbol = normalize_symbol(symbol)
    mexc_interval = INTERVAL_MAP.get(str(interval), str(interval))

    now = int(time.time())
    step = SECONDS_MAP.get(mexc_interval, 900)
    requested_limit = max(int(limit), 1)
    start = now - (step * max(requested_limit, 50))

    data = _get(
        f"/api/v1/contract/kline/{mexc_symbol}",
        {
            "interval": mexc_interval,
            "start": start,
            "end": now,
        },
    )

    payload = data.get("data") if data.get("success") else None
    if not isinstance(payload, dict):
        logging.warning("MEXC kline veri yok | %s %s", symbol, interval)
        return []

    times = payload.get("time") or []
    opens = payload.get("open") or []
    highs = payload.get("high") or []
    lows = payload.get("low") or []
    closes = payload.get("close") or []
    volumes = payload.get("vol") or payload.get("volume") or []

    size = min(len(times), len(opens), len(highs), len(lows), len(closes), len(volumes))
    rows: List[Dict[str, float]] = []

    for i in range(size):
        try:
            open_time = float(times[i]) * 1000.0
            close_time = open_time + (step * 1000.0) - 1.0
            rows.append({
                "open_time": open_time,
                "close_time": close_time,
                "time": open_time,
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "volume": float(volumes[i]),
            })
        except Exception:
            continue

    return rows[-requested_limit:]


fetch_symbols = get_symbols
fetch_ticker = get_ticker
fetch_klines = get_klines


def get_valid_futures_symbols():
    return get_symbols()


def get_kline_limit(tf=None, *args, **kwargs):
    return 200
