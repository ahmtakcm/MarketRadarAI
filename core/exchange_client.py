import logging
import time
from typing import Any, Dict, List, Optional

import requests

MEXC_BASE = "https://contract.mexc.com"

INTERVAL_MAP = {
    "1m": "Min1",
    "3m": "Min5",      # MEXC futures tarafında Min3 yok; güvenli fallback
    "5m": "Min5",
    "15m": "Min15",
    "30m": "Min30",
    "1h": "Min60",
    "4h": "Hour4",
    "1d": "Day1",
    "1w": "Week1",
}

_session = requests.Session()


def _get(path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
    url = f"{MEXC_BASE}{path}"
    try:
        r = _session.get(url, params=params or {}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            return {"success": False, "data": None, "message": "non-dict response"}
        return data
    except Exception as e:
        logging.warning("MEXC GET hata | path=%s params=%s err=%s", path, params, e)
        return {"success": False, "data": None, "message": str(e)}


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
        logging.warning("MEXC sembol listesi alınamadı")
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

        # USDT perpetual ağırlıklı tarama
        if quote and str(quote).upper() != "USDT":
            continue

        # state yoksa eleme yapma; varsa aktif olmayanları dışla
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


def get_klines(symbol: str, interval: str = "15m", limit: int = 200) -> List[List[float]]:
    mexc_symbol = normalize_symbol(symbol)
    mexc_interval = INTERVAL_MAP.get(str(interval), str(interval))

    # MEXC futures kline start/end saniye bazlı çalışır.
    now = int(time.time())
    seconds_map = {
        "Min1": 60,
        "Min5": 300,
        "Min15": 900,
        "Min30": 1800,
        "Min60": 3600,
        "Hour4": 14400,
        "Day1": 86400,
        "Week1": 604800,
    }
    step = seconds_map.get(mexc_interval, 900)
    start = now - (step * max(int(limit), 50))

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
    vols = payload.get("vol") or payload.get("volume") or []

    size = min(len(times), len(opens), len(highs), len(lows), len(closes), len(vols))
    rows: List[List[float]] = []

    for i in range(size):
        try:
            ts = float(times[i]) * 1000.0
            rows.append({
                "open_time": ts,
                "close_time": ts,
                "time": ts,
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "volume": float(vols[i]),
            })
        except Exception:
            continue

    return rows[-int(limit):]


# Eski kod farklı isimler çağırıyorsa kırılmasın diye aliaslar
fetch_symbols = get_symbols
fetch_ticker = get_ticker
fetch_klines = get_klines

# Backward compatibility for existing scanner.py
def get_valid_futures_symbols():
    return get_symbols()


def get_kline_limit(tf=None, *args, **kwargs):
    return 200
