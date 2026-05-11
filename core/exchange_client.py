import logging
import time

import requests

MEXC_BASE = "https://contract.mexc.com"

INTERVAL_MAP = {
    "1m": "Min1",
    "3m": "Min5",  # MEXC has no Min3; use Min5 fallback
    "5m": "Min5",
    "15m": "Min15",
    "30m": "Min30",
    "1h": "Min60",
    "4h": "Hour4",
    "1d": "Day1",
    "1w": "Week1",
}

INTERVAL_SECONDS = {
    "1m": 60,
    "3m": 5 * 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}

KLINE_LIMITS = {
    "15m": 500,
    "1h": 750,
    "4h": 750,
    "1d": 500,
    "1w": 300,
}


def to_mexc_symbol(symbol: str) -> str:
    symbol = str(symbol).upper().strip()
    if "_" in symbol:
        return symbol
    if symbol.endswith("USDT"):
        return symbol[:-4] + "_USDT"
    return symbol


def from_mexc_symbol(symbol: str) -> str:
    return str(symbol).upper().replace("_", "")


def get_kline_limit(interval):
    return KLINE_LIMITS.get(str(interval).lower(), 500)


def _get_json(url, params=None, retries=3, timeout=15):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")

            data = r.json()
            if not data.get("success", False):
                raise RuntimeError(f"MEXC success=false: {data}")

            return data

        except Exception as e:
            last_error = e
            logging.warning("MEXC API request failed attempt %s/%s | %s", attempt, retries, e)
            time.sleep(1.5)

    raise RuntimeError(f"MEXC API request failed | url={url} | params={params} | error={last_error}")


def get_valid_futures_symbols():
    url = f"{MEXC_BASE}/api/v1/contract/detail"
    data = _get_json(url)
    items = data.get("data", []) or []

    symbols = []
    for item in items:
        sym = item.get("symbol")
        if not sym:
            continue

        plain = from_mexc_symbol(sym)
        if plain.endswith("USDT"):
            symbols.append(plain)

    return sorted(set(symbols))


def fetch_klines(symbol, interval, limit):
    interval = str(interval).lower().strip()
    mexc_interval = INTERVAL_MAP.get(interval)
    if not mexc_interval:
        raise ValueError(f"Desteklenmeyen MEXC interval: {interval}")

    mexc_symbol = to_mexc_symbol(symbol)
    url = f"{MEXC_BASE}/api/v1/contract/kline/{mexc_symbol}"
    params = {
        "interval": mexc_interval,
    }

    data = _get_json(url, params=params)
    payload = data.get("data", {}) or {}

    times = payload.get("time", []) or []
    opens = payload.get("open", []) or []
    highs = payload.get("high", []) or []
    lows = payload.get("low", []) or []
    closes = payload.get("close", []) or []
    vols = payload.get("vol", []) or []

    n = min(len(times), len(opens), len(highs), len(lows), len(closes), len(vols))
    rows = []
    interval_seconds = INTERVAL_SECONDS.get(interval)
    if not interval_seconds:
        raise ValueError(f"Unsupported MEXC interval seconds: {interval}")

    now_ms = int(time.time() * 1000)

    for i in range(n):
        open_time_ms = int(times[i]) * 1000
        close_time_ms = open_time_ms + (interval_seconds * 1000) - 1

        # MEXC can include the currently forming candle. The scanner must only
        # consume closed candles to avoid premature signals.
        if close_time_ms >= now_ms:
            continue

        rows.append([
            open_time_ms,
            str(opens[i]),
            str(highs[i]),
            str(lows[i]),
            str(closes[i]),
            str(vols[i]),
            close_time_ms,
            "0",
            0,
            "0",
            "0",
            "0",
        ])

    if limit:
        rows = rows[-int(limit):]

    return rows

# Normalize MEXC adapter candles for scanner/indicator_engine.
_fetch_klines_raw_mexc = fetch_klines

def fetch_klines(symbol, interval, limit):
    raw_candles = _fetch_klines_raw_mexc(symbol, interval, limit)
    candles = []

    for c in raw_candles or []:
        if isinstance(c, dict):
            candles.append(c)
            continue

        timestamp = int(c[0])
        candles.append({
            "timestamp": timestamp,
            "open_time": timestamp,
            "close_time": int(c[6]) if len(c) > 6 else timestamp,
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        })

    return candles
