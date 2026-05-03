from core.indicators import ema_last


def _cached_ema(context, closes, length):
    cache = context.setdefault("indicator_cache", {})
    key = f"ema_{length}"

    if key not in cache:
        cache[key] = ema_last(closes, length)

    return cache[key]


def evaluate(context, settings=None):
    settings = settings or {}
    candles = context.get("candles") or []
    closes = [c["close"] for c in candles]

    fast = int(settings.get("fast", 8))
    slow = int(settings.get("slow", 21))

    fast_ema = _cached_ema(context, closes, fast)
    slow_ema = _cached_ema(context, closes, slow)

    if fast_ema is None or slow_ema is None:
        return None, None

    if fast_ema > slow_ema:
        return "LONG", f"EMA{fast} EMA{slow} üstünde"

    if fast_ema < slow_ema:
        return "SHORT", f"EMA{fast} EMA{slow} altında"

    return None, None
