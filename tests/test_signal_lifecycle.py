from core.signal_lifecycle import build_pending_signal_record, build_signal_dedupe_key


def test_signal_lifecycle_dedupe_key_contract_is_stable():
    assert (
        build_signal_dedupe_key("BTCUSDT", "15m", "FiBB Bands", 123456, "LONG")
        == "BTCUSDT_15m_FiBB Bands_123456_LONG"
    )


def test_signal_lifecycle_pending_record_contract_matches_existing_state_shape():
    record = build_pending_signal_record(
        symbol="BTCUSDT",
        timeframe="15m",
        strategy="FiBB Bands",
        signal="LONG",
        reason="breakout",
        levels={"close": 100.5, "close_time": 123456},
        target_horizons=[1, 3, 5],
        timestamp=99,
    )

    assert record == {
        "timestamp": 99,
        "id": "BTCUSDT_15m_FiBB Bands_123456_LONG",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "strategy": "FiBB Bands",
        "signal": "LONG",
        "reason": "breakout",
        "entry_price": 100.5,
        "close_time": 123456,
        "target_horizons": [1, 3, 5],
    }
