PHASE_EXTREME_OVERSOLD = "EXTREME_OVERSOLD"
PHASE_EXTREME_OVERBOUGHT = "EXTREME_OVERBOUGHT"
PHASE_RECOVERY = "RECOVERY"
PHASE_TREND_BUILDING = "TREND_BUILDING"
PHASE_TREND_EXPANSION = "TREND_EXPANSION"


def _phase_candidate(phase, reason, *, score=None, quality="WATCH"):
    candidate = {
        "candidate_type": "phase",
        "signal": phase,
        "phase": phase,
        "reason": reason,
        "quality": quality,
    }
    if score is not None:
        candidate["score"] = score
    return candidate


def _trade_candidate(signal, phase, notes, score, stop_loss):
    quality = "HIGH" if score >= 65 else "MEDIUM" if score >= 45 else "LOW"
    return {
        "candidate_type": "trade",
        "signal": signal,
        "phase": phase,
        "reason": "\n".join([phase, *notes]),
        "score": score,
        "quality": quality,
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
    prev_close = levels["prev_close"]
    ema8 = levels["ema8"]
    ema21 = levels["ema21"]
    ema89 = levels["ema89"]
    ema244 = levels["ema244"]
    center = levels["center"]

    lower_fib5 = levels.get("lower_fib5")
    upper_fib5 = levels.get("upper_fib5")

    if lower_fib5 is not None and close <= levels["lower_fib4"]:
        return [
            _phase_candidate(
                PHASE_EXTREME_OVERSOLD,
                "Fib4-5 altı\nPanik satış bölgesi\nReversal takip ediliyor",
                quality="WATCH",
            )
        ]

    if upper_fib5 is not None and close >= levels["upper_fib4"]:
        return [
            _phase_candidate(
                PHASE_EXTREME_OVERBOUGHT,
                "Fib4-5 üstü\nPanik alış bölgesi\nReversal takip ediliyor",
                quality="WATCH",
            )
        ]

    long_phase, long_score = _long_phase(ema8, ema21, ema89, ema244)
    short_phase, short_score = _short_phase(ema8, ema21, ema89, ema244)

    if (
        long_phase in {PHASE_TREND_BUILDING, PHASE_TREND_EXPANSION}
        and _in_lower_pullback_zone(levels)
        and prev_close < center
        and close > center
    ):
        return [
            _trade_candidate(
                "LONG",
                long_phase,
                ["Fib pullback", "EMA34 geri dönüş"],
                long_score + 25,
                levels["lower_fib3"],
            )
        ]

    if (
        short_phase in {PHASE_TREND_BUILDING, PHASE_TREND_EXPANSION}
        and _in_upper_pullback_zone(levels)
        and prev_close > center
        and close < center
    ):
        return [
            _trade_candidate(
                "SHORT",
                short_phase,
                ["Fib pullback", "EMA34 geri dönüş"],
                short_score + 25,
                levels["upper_fib3"],
            )
        ]

    if long_phase == PHASE_RECOVERY:
        return [
            _phase_candidate(
                PHASE_RECOVERY,
                "EMA8 EMA21 üzerine geçti\nErken toparlanma\nTrend teyidi bekleniyor",
                score=15,
            )
        ]

    if short_phase == PHASE_RECOVERY:
        return [
            _phase_candidate(
                PHASE_RECOVERY,
                "EMA8 EMA21 altına indi\nErken zayıflama\nTrend teyidi bekleniyor",
                score=15,
            )
        ]

    return []
