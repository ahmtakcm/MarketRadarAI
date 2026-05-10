from core.indicators import atr, ema_last

STRATEGY_KEY = "fibb_bands"
STRATEGY_NAME = "FiBB Bands"


def _cached_ema(context, closes, length):
    cache = context.setdefault("indicator_cache", {})
    key = f"ema_{length}"

    if key not in cache:
        cache[key] = ema_last(closes, length)

    return cache[key]


def _cached_atr(context, candles, length):
    cache = context.setdefault("indicator_cache", {})
    key = f"atr_{length}"

    if key not in cache:
        cache[key] = atr(candles, length)

    return cache[key]


def build_context(context):
    candles = context.get("candles") or []

    if len(candles) < 245:
        return None

    closes = [c["close"] for c in candles]

    ema8 = _cached_ema(context, closes, 8)
    ema21 = _cached_ema(context, closes, 21)
    ema89 = _cached_ema(context, closes, 89)
    ema244 = _cached_ema(context, closes, 244)
    center = _cached_ema(context, closes, 34)
    atr_val = _cached_atr(context, candles, 20)

    if None in (ema8, ema21, ema89, ema244, center, atr_val):
        return None

    last = candles[-1]
    prev = candles[-2]
    atr_band = atr_val * 2

    return {
        "close": last["close"],
        "high": last["high"],
        "low": last["low"],
        "prev_close": prev["close"],
        "ema8": ema8,
        "ema21": ema21,
        "ema89": ema89,
        "ema244": ema244,
        "center": center,
        "atr": atr_val,
        "upper_fib1": center + atr_band * 0.618,
        "lower_fib1": center - atr_band * 0.618,
        "upper_fib2": center + atr_band * 1.0,
        "lower_fib2": center - atr_band * 1.0,
        "upper_fib3": center + atr_band * 1.618,
        "lower_fib3": center - atr_band * 1.618,
        "upper_fib4": center + atr_band * 2.618,
        "lower_fib4": center - atr_band * 2.618,
        "upper_fib5": center + atr_band * 3.618,
        "lower_fib5": center - atr_band * 3.618,
    }


def evaluate(context, settings=None):
    ctx = build_context(context)
    if not ctx:
        return None, None

    close = ctx["close"]
    high = ctx["high"]
    low = ctx["low"]
    prev_close = ctx["prev_close"]

    ema8 = ctx["ema8"]
    ema21 = ctx["ema21"]
    ema89 = ctx["ema89"]
    ema244 = ctx["ema244"]
    center = ctx["center"]
    atr_val = ctx["atr"]

    bullish = ema8 > ema21 > ema89 > ema244
    bearish = ema8 < ema21 < ema89 < ema244

    ema_distance_ok = abs(ema8 - ema21) > atr_val * 0.20
    break_strength = abs(close - center)
    strong_break = break_strength > atr_val * 0.50

    # Aşırı genişleme bölgeleri: takip edilir ama yeni giriş sinyali verilmez.
    if high >= ctx["upper_fib4"]:
        return "EXTREME_OVERBOUGHT", "FiBB Bands: aşırı alım bölgesi, Fib4 temas"

    if low <= ctx["lower_fib4"]:
        return "EXTREME_OVERSOLD", "FiBB Bands: aşırı satım bölgesi, Fib4 temas"

    # Fib3 dışı geç kalmış bölge: yeni giriş üretme.
    if close >= ctx["upper_fib3"] or close <= ctx["lower_fib3"]:
        return None, None

    # EXTREME artık sadece gerçekten güçlü kırılımda gelir.
    if (
        bullish
        and prev_close <= center
        and close > center
        and close < ctx["upper_fib2"]
        and strong_break
        and ema_distance_ok
    ):
        return "EXTREME_LONG", "FiBB Bands: güçlü yükseliş trendi + güçlü merkez kırılımı + EMA mesafe onayı"

    if (
        bearish
        and prev_close >= center
        and close < center
        and close > ctx["lower_fib2"]
        and strong_break
        and ema_distance_ok
    ):
        return "EXTREME_SHORT", "FiBB Bands: güçlü düşüş trendi + güçlü merkez kırılımı + EMA mesafe onayı"

    # Normal sinyal fallback.
    if bullish and prev_close <= center and close > center and close < ctx["upper_fib2"]:
        return "LONG", "FiBB Bands: yükseliş trendi + ilk merkez yukarı kırılımı"

    if bearish and prev_close >= center and close < center and close > ctx["lower_fib2"]:
        return "SHORT", "FiBB Bands: düşüş trendi + ilk merkez aşağı kırılımı"

    return None, None
