import logging
import time

import requests

from config import BINANCE_FAPI_BASE


def safe_get(url, params=None, timeout=20, retries=3, sleep_seconds=1.5):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)

            if r.status_code == 200:
                return r

            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
            logging.warning("Binance API başarısız deneme %s/%s | %s", attempt, retries, last_error)

        except Exception as e:
            last_error = str(e)
            logging.warning("Binance API bağlantı hatası %s/%s | %s", attempt, retries, last_error)

        if attempt < retries:
            time.sleep(sleep_seconds)

    logging.error("Binance API isteği başarısız oldu | url=%s | params=%s | hata=%s", url, params, last_error)
    return None


def get_valid_futures_symbols():
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/exchangeInfo"
    r = safe_get(url, timeout=20, retries=3)

    if r is None:
        return set()

    data = r.json()

    valid_symbols = set()
    for item in data.get("symbols", []):
        symbol = item.get("symbol")

        if item.get("status") != "TRADING":
            continue

        if not symbol:
            continue

        # Sadece temiz USDT futures çiftleri.
        # USDC, tarihli kontratlar, unicode/garip semboller ve özel pairler elenir.
        if not symbol.endswith("USDT"):
            continue

        if not symbol.isascii() or not symbol.replace("USDT", "").isalnum():
            continue

        valid_symbols.add(symbol)

    return valid_symbols


def get_kline_limit(interval):
    if interval == "1w":
        return 300
    if interval == "1d":
        return 500
    if interval == "1h":
        return 750
    if interval == "30m":
        return 750
    return 500


def fetch_klines(symbol, interval, limit):
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    r = safe_get(url, params=params, timeout=20, retries=3)

    if r is None:
        return None

    try:
        data = r.json()
    except Exception as e:
        logging.warning("Kline JSON parse hatası | %s %s | %s", symbol, interval, e)
        return None

    if not isinstance(data, list) or len(data) < 60:
        logging.warning("Kline veri yetersiz | %s %s | len=%s", symbol, interval, len(data) if isinstance(data, list) else "invalid")
        return None

    # Son satır çoğu zaman açık mumdur; kapalı mumları kullan.
    closed_rows = data[:-1]
    if len(closed_rows) < 50:
        logging.warning("Kapalı mum sayısı yetersiz | %s %s | len=%s", symbol, interval, len(closed_rows))
        return None

    candles = []
    for row in closed_rows:
        try:
            candles.append({
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "close_time": int(row[6]),
            })
        except Exception as e:
            logging.warning("Kline satırı parse edilemedi | %s %s | %s", symbol, interval, e)
            continue

    if len(candles) < 50:
        return None

    return candles
