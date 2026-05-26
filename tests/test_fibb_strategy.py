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


def test_fibb_strategy_extreme_oversold_is_phase_only():
    signals = fibb_strategy.evaluate({"levels": _levels(close=70.0, low=69.0)})

    assert signals == [
        {
            "candidate_type": "phase",
            "signal": "EXTREME_OVERSOLD",
            "phase": "EXTREME_OVERSOLD",
            "reason": "Fib4-5 altı\nPanik satış bölgesi\nReversal takip ediliyor",
            "quality": "WATCH",
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
            "reason": "TREND_EXPANSION\nFib pullback\nEMA34 geri dönüş",
            "score": 65,
            "quality": "HIGH",
            "stop_loss": 83.82,
        }
    ]


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
            "reason": "TREND_EXPANSION\nFib pullback\nEMA34 geri dönüş",
            "score": 65,
            "quality": "HIGH",
            "stop_loss": 116.18,
        }
    ]
