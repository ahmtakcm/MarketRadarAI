def ema_last(values, length):
    if len(values) < length:
        return None

    multiplier = 2 / (length + 1)
    ema_val = sum(values[:length]) / length

    for price in values[length:]:
        ema_val = (price - ema_val) * multiplier + ema_val

    return ema_val


def rsi_last(values, length=14):
    if len(values) < length + 1:
        return None

    gains = []
    losses = []

    for i in range(-length, 0):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles, length=20):
    trs = []

    for i, c in enumerate(candles):
        high = c["high"]
        low = c["low"]

        if i == 0:
            tr = high - low
        else:
            prev_close = candles[i - 1]["close"]
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
        trs.append(tr)

    if len(trs) < length:
        return None

    return sum(trs[-length:]) / length


def build_levels(candles):
    closes = [c["close"] for c in candles]

    ema8 = ema_last(closes, 8)
    ema21 = ema_last(closes, 21)
    ema89 = ema_last(closes, 89)
    ema244 = ema_last(closes, 244)
    center = ema_last(closes, 34)
    atr_val = atr(candles, 20)
    rsi14 = rsi_last(closes, 14)

    if None in (ema8, ema21, ema89, ema244, center, atr_val):
        return None

    atr_band = atr_val * 2
    last = candles[-1]
    prev = candles[-2]

    return {
        "close_time": last["close_time"],
        "close": last["close"],
        "high": last["high"],
        "low": last["low"],
        "prev_close": prev["close"],
        "ema8": ema8,
        "ema21": ema21,
        "ema89": ema89,
        "ema244": ema244,
        "center": center,
        "rsi14": rsi14,
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
