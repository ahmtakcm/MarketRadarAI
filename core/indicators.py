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
                abs(low - prev_close),
            )

        trs.append(tr)

    if len(trs) < length:
        return None

    return sum(trs[-length:]) / length


def volume_stats(candles, length=20):
    volumes = [float(c.get("volume", 0) or 0) for c in candles]

    if not volumes:
        return {
            "volume": 0.0,
            "avg_volume": None,
            "volume_ratio": None,
        }

    volume = volumes[-1]

    if len(volumes) < length:
        return {
            "volume": volume,
            "avg_volume": None,
            "volume_ratio": None,
        }

    avg_volume = sum(volumes[-length:]) / length
    ratio = volume / avg_volume if avg_volume > 0 else None

    return {
        "volume": volume,
        "avg_volume": avg_volume,
        "volume_ratio": ratio,
    }
