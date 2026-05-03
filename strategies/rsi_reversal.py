from core.indicators import rsi_last


def _cached_rsi(context, closes, length):
    cache = context.setdefault("indicator_cache", {})
    key = f"rsi_{length}"

    if key not in cache:
        cache[key] = rsi_last(closes, length)

    return cache[key]


def evaluate(context, settings=None):
    settings = settings or {}
    candles = context.get("candles") or []
    closes = [c["close"] for c in candles]

    length = int(settings.get("length", 14))
    oversold = float(settings.get("oversold", 30))
    overbought = float(settings.get("overbought", 70))

    rsi = _cached_rsi(context, closes, length)
    if rsi is None:
        return None, None

    if rsi <= oversold:
        return "LONG", f"RSI aşırı satım ({rsi:.2f})"

    if rsi >= overbought:
        return "SHORT", f"RSI aşırı alım ({rsi:.2f})"

    return None, None
