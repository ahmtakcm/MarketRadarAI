PHASE_EXTREME_OVERSOLD = "EXTREME_OVERSOLD"
PHASE_EXTREME_OVERBOUGHT = "EXTREME_OVERBOUGHT"
PHASE_RECOVERY = "RECOVERY"
PHASE_TREND_BUILDING = "TREND_BUILDING"
PHASE_TREND_EXPANSION = "TREND_EXPANSION"
PHASE_FAILED_BREAKOUT = "FAILED_BREAKOUT"

ALERT_WATCH_PHASE = "WATCH_PHASE"
ALERT_EARLY_LONG = "EARLY_LONG"
ALERT_EARLY_SHORT = "EARLY_SHORT"
ALERT_CONFIRMED_LONG = "CONFIRMED_LONG"
ALERT_CONFIRMED_SHORT = "CONFIRMED_SHORT"
ALERT_EXPANSION_LONG = "EXPANSION_LONG"
ALERT_EXPANSION_SHORT = "EXPANSION_SHORT"
ALERT_FAILED_BREAKOUT = "FAILED_BREAKOUT"

SWING_LOOKBACK = 20


def _phase_candidate(phase, reason, *, score=None, quality="WATCH", alert_class=ALERT_WATCH_PHASE):
    candidate = {
        "candidate_type": "phase",
        "signal": phase,
        "phase": phase,
        "reason": reason,
        "quality": quality,
        "alert_class": alert_class,
    }
    if score is not None:
        candidate["score"] = score
    return candidate


def _quality(score):
    if score >= 65:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def _trade_candidate(signal, phase, alert_class, notes, score, stop_loss):
    return {
        "candidate_type": "trade",
        "signal": signal,
        "phase": phase,
        "alert_class": alert_class,
        "reason": "\n".join([alert_class, phase, *notes]),
        "score": score,
        "quality": _quality(score),
        "stop_loss": stop_loss,
    }


def _long_phase(ema8, ema21, ema89, ema244):
    if ema8 > ema21 > ema89 > ema244:
        return PHASE_TREND_EXPANSION, 40
    if ema8 > ema21 > ema89:
        return PHASE_TREND_BUILDING, 25
    if ema8 > ema21 and ema21 < ema89:
        return PHASE_RECOVERY, 15
    if ema8 > ema21:
        return "MOMENTUM_START", 10
    return None, 0


def _short_phase(ema8, ema21, ema89, ema244):
    if ema8 < ema21 < ema89 < ema244:
        return PHASE_TREND_EXPANSION, 40
    if ema8 < ema21 < ema89:
        return PHASE_TREND_BUILDING, 25
    if ema8 < ema21 and ema21 > ema89:
        return PHASE_RECOVERY, 15
    if ema8 < ema21:
        return "MOMENTUM_START", 10
    return None, 0


def _in_lower_pullback_zone(levels):
    low = levels["low"]
    close = levels["close"]
    lower_fib1 = levels["lower_fib1"]
    lower_fib2 = levels["lower_fib2"]
    return lower_fib2 <= low <= lower_fib1 or lower_fib2 <= close <= lower_fib1


def _in_upper_pullback_zone(levels):
    high = levels["high"]
    close = levels["close"]
    upper_fib1 = levels["upper_fib1"]
    upper_fib2 = levels["upper_fib2"]
    return upper_fib1 <= high <= upper_fib2 or upper_fib1 <= close <= upper_fib2


def _swing_levels(candles, lookback=SWING_LOOKBACK):
    prior = list(candles or [])[-lookback - 1 : -1]
    if not prior:
        return None, None
    highs = [c.get("high") for c in prior if c.get("high") is not None]
    lows = [c.get("low") for c in prior if c.get("low") is not None]
    return (max(highs) if highs else None, min(lows) if lows else None)


def _failed_expansion_candidate(levels, long_phase, short_phase):
    close = levels["close"]
    center = levels["center"]

    if long_phase == PHASE_TREND_EXPANSION and close <= center:
        return _phase_candidate(
            PHASE_FAILED_BREAKOUT,
            "FAILED_BREAKOUT\nTREND_EXPANSION dizilimi var\nFiyat EMA34 merkeze geri dondu",
            score=20,
            quality="LOW",
            alert_class=ALERT_FAILED_BREAKOUT,
        )

    if short_phase == PHASE_TREND_EXPANSION and close >= center:
        return _phase_candidate(
            PHASE_FAILED_BREAKOUT,
            "FAILED_BREAKOUT\nTREND_EXPANSION dizilimi var\nFiyat EMA34 merkeze geri dondu",
            score=20,
            quality="LOW",
            alert_class=ALERT_FAILED_BREAKOUT,
        )

    return None


def _long_trade(levels, phase, phase_score, swing_high):
    close = levels["close"]
    prev_close = levels["prev_close"]
    center = levels["center"]
    ema89 = levels["ema89"]

    if not (
        phase in {PHASE_TREND_BUILDING, PHASE_TREND_EXPANSION}
        and _in_lower_pullback_zone(levels)
        and prev_close < center
        and close > center
    ):
        return None

    score = phase_score + 25
    notes = ["EMA34 ustunde tutundu"]
    alert_class = ALERT_EARLY_LONG if phase == PHASE_TREND_BUILDING else ALERT_CONFIRMED_LONG

    if levels["low"] <= levels["lower_fib1"]:
        score += 5
        notes.append("Fib1 duzeltme tamamlandi")

    if close > ema89:
        score += 5
        notes.append("EMA89 direnc kirilimi")

    if swing_high is not None and close > swing_high:
        score += 10
        notes.append("Onceki swing high kirildi")
        if phase == PHASE_TREND_EXPANSION:
            alert_class = ALERT_EXPANSION_LONG

    return _trade_candidate("LONG", phase, alert_class, notes, score, levels["lower_fib3"])


def _short_trade(levels, phase, phase_score, swing_low):
    close = levels["close"]
    prev_close = levels["prev_close"]
    center = levels["center"]
    ema89 = levels["ema89"]

    if not (
        phase in {PHASE_TREND_BUILDING, PHASE_TREND_EXPANSION}
        and _in_upper_pullback_zone(levels)
        and prev_close > center
        and close < center
    ):
        return None

    score = phase_score + 25
    notes = ["EMA34 altinda tutundu"]
    alert_class = ALERT_EARLY_SHORT if phase == PHASE_TREND_BUILDING else ALERT_CONFIRMED_SHORT

    if levels["high"] >= levels["upper_fib1"]:
        score += 5
        notes.append("Fib1 tepkisi tamamlandi")

    if close < ema89:
        score += 5
        notes.append("EMA89 destek kirilimi")

    if swing_low is not None and close < swing_low:
        score += 10
        notes.append("Onceki swing low kirildi")
        if phase == PHASE_TREND_EXPANSION:
            alert_class = ALERT_EXPANSION_SHORT

    return _trade_candidate("SHORT", phase, alert_class, notes, score, levels["upper_fib3"])


def evaluate(context, settings=None):
    levels = context.get("levels") or {}
    required = [
        "close",
        "high",
        "low",
        "prev_close",
        "ema8",
        "ema21",
        "ema89",
        "ema244",
        "center",
        "upper_fib1",
        "upper_fib2",
        "upper_fib3",
        "upper_fib4",
        "lower_fib1",
        "lower_fib2",
        "lower_fib3",
        "lower_fib4",
    ]
    if any(levels.get(key) is None for key in required):
        return []

    close = levels["close"]
    ema8 = levels["ema8"]
    ema21 = levels["ema21"]
    ema89 = levels["ema89"]
    ema244 = levels["ema244"]

    lower_fib5 = levels.get("lower_fib5")
    upper_fib5 = levels.get("upper_fib5")

    if lower_fib5 is not None and close <= levels["lower_fib4"]:
        return [
            _phase_candidate(
                PHASE_EXTREME_OVERSOLD,
                "EXTREME_OVERSOLD\nFib4-5 alti\nPanik satis bolgesi\nReversal takip ediliyor",
                quality="WATCH",
            )
        ]

    if upper_fib5 is not None and close >= levels["upper_fib4"]:
        return [
            _phase_candidate(
                PHASE_EXTREME_OVERBOUGHT,
                "EXTREME_OVERBOUGHT\nFib4-5 ustu\nPanik alis bolgesi\nReversal takip ediliyor",
                quality="WATCH",
            )
        ]

    long_phase, long_score = _long_phase(ema8, ema21, ema89, ema244)
    short_phase, short_score = _short_phase(ema8, ema21, ema89, ema244)

    failed_expansion = _failed_expansion_candidate(levels, long_phase, short_phase)
    if failed_expansion:
        return [failed_expansion]

    swing_high, swing_low = _swing_levels(context.get("candles") or [])

    long_candidate = _long_trade(levels, long_phase, long_score, swing_high)
    if long_candidate:
        return [long_candidate]

    short_candidate = _short_trade(levels, short_phase, short_score, swing_low)
    if short_candidate:
        return [short_candidate]

    if long_phase == PHASE_RECOVERY:
        return [
            _phase_candidate(
                PHASE_RECOVERY,
                "RECOVERY\nEMA8 EMA21 uzerine gecti\nEMA89 ilk direnc olarak izleniyor",
                score=20 if close > ema89 else 15,
            )
        ]

    if short_phase == PHASE_RECOVERY:
        return [
            _phase_candidate(
                PHASE_RECOVERY,
                "RECOVERY\nEMA8 EMA21 altina indi\nEMA89 ilk destek olarak izleniyor",
                score=20 if close < ema89 else 15,
            )
        ]

    return []
