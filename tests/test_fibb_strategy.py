from strategies import fibb_strategy


def _levels(**overrides):
    base = {
        "close_time": 123,
        "close": 100.0,
        "high": 101.0,
        "low": 99.0,
        "prev_close": 99.0,
        "ema8": 108.0,
        "ema21": 106.0,
        "ema89": 104.0,
        "ema244": 102.0,
        "center": 100.0,
        "upper_fib1": 105.0,
        "lower_fib1": 95.0,
        "upper_fib2": 110.0,
        "lower_fib2": 90.0,
        "upper_fib3": 116.18,
        "lower_fib3": 83.82,
        "upper_fib4": 126.18,
        "lower_fib4": 73.82,
        "upper_fib5": 136.18,
        "lower_fib5": 63.82,
    }
    base.update(overrides)
    return base


def _candles(*, swing_high=100.0, swing_low=90.0):
    return [
        {"high": swing_high - 2, "low": swing_low + 2},
        {"high": swing_high, "low": swing_low},
        {"high": swing_high - 1, "low": swing_low + 1},
    ]


def test_fibb_strategy_extreme_oversold_is_phase_only():
    signals = fibb_strategy.evaluate({"levels": _levels(close=70.0, low=69.0)})

    assert signals == [
        {
            "candidate_type": "phase",
            "signal": "EXTREME_OVERSOLD",
            "phase": "EXTREME_OVERSOLD",
            "reason": "EXTREME_OVERSOLD\nFib4-5 alti\nPanik satis bolgesi\nReversal takip ediliyor",
            "quality": "WATCH",
            "alert_class": "WATCH_PHASE",
        }
    ]


def test_fibb_strategy_recovery_tracks_ema89_as_first_resistance():
    signals = fibb_strategy.evaluate({
        "levels": _levels(
            ema8=102.0,
            ema21=101.0,
            ema89=104.0,
            ema244=105.0,
        )
    })

    assert signals == [
        {
            "candidate_type": "phase",
            "signal": "RECOVERY",
            "phase": "RECOVERY",
            "reason": "RECOVERY\nEMA8 EMA21 uzerine gecti\nEMA89 ilk direnc olarak izleniyor",
            "quality": "WATCH",
            "alert_class": "WATCH_PHASE",
            "score": 15,
        }
    ]


def test_fibb_strategy_long_uses_expansion_phase_and_lower_fib3_stop():
    signals = fibb_strategy.evaluate({
        "levels": _levels(
            close=101.0,
            low=94.0,
            prev_close=99.0,
        )
    })

    assert signals == [
        {
            "candidate_type": "trade",
            "signal": "LONG",
            "phase": "TREND_EXPANSION",
            "alert_class": "CONFIRMED_LONG",
            "reason": "CONFIRMED_LONG\nTREND_EXPANSION\nEMA34 ustunde tutundu\nFib1 duzeltme tamamlandi",
            "score": 70,
            "quality": "HIGH",
            "stop_loss": 83.82,
        }
    ]


def test_fibb_strategy_long_expansion_strengthens_on_swing_high_break():
    signals = fibb_strategy.evaluate({
        "levels": _levels(
            close=107.0,
            low=94.0,
            prev_close=99.0,
            ema89=104.0,
        ),
        "candles": _candles(swing_high=106.0),
    })

    assert signals[0]["alert_class"] == "EXPANSION_LONG"
    assert signals[0]["score"] == 85
    assert "+ Onceki swing high kirildi" not in signals[0]["reason"]
    assert "Onceki swing high kirildi" in signals[0]["reason"]
    assert "EMA89 direnc kirilimi" in signals[0]["reason"]


def test_fibb_strategy_short_uses_upper_fib3_stop():
    signals = fibb_strategy.evaluate({
        "levels": _levels(
            close=99.0,
            high=106.0,
            prev_close=101.0,
            ema8=92.0,
            ema21=94.0,
            ema89=96.0,
            ema244=98.0,
        )
    })

    assert signals == [
        {
            "candidate_type": "trade",
            "signal": "SHORT",
            "phase": "TREND_EXPANSION",
            "alert_class": "CONFIRMED_SHORT",
            "reason": "CONFIRMED_SHORT\nTREND_EXPANSION\nEMA34 altinda tutundu\nFib1 tepkisi tamamlandi",
            "score": 70,
            "quality": "HIGH",
            "stop_loss": 116.18,
        }
    ]


def test_fibb_strategy_failed_expansion_stays_phase_only():
    signals = fibb_strategy.evaluate({
        "levels": _levels(
            close=99.0,
            prev_close=101.0,
        )
    })

    assert signals == [
        {
            "candidate_type": "phase",
            "signal": "FAILED_BREAKOUT",
            "phase": "FAILED_BREAKOUT",
            "reason": "FAILED_BREAKOUT\nTREND_EXPANSION dizilimi var\nFiyat EMA34 merkeze geri dondu",
            "quality": "LOW",
            "alert_class": "FAILED_BREAKOUT",
            "score": 20,
        }
    ]
