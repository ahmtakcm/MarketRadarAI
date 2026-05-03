import time
from config import SIGNAL_HORIZONS_BARS, PERFORMANCE_LOG_PATH
from core.state_store import append_jsonl


def register_signal(state, symbol, timeframe, strategy_name, signal, reason, levels):
    signal_id = f"{symbol}_{timeframe}_{strategy_name}_{levels['close_time']}_{signal}"

    for item in state.get("pending_signals", []):
        if item["id"] == signal_id:
            return

    row = {
        "timestamp": int(time.time()),
        "id": signal_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": strategy_name,
        "signal": signal,
        "reason": reason,
        "entry_price": levels["close"],
        "close_time": levels["close_time"],
        "target_horizons": SIGNAL_HORIZONS_BARS
    }

    state.setdefault("pending_signals", []).append(row)


def finalize_pending_signals(state, fetch_klines_fn, get_limit_fn):
    pending = state.get("pending_signals", [])
    still_pending = []

    for item in pending:
        symbol = item["symbol"]
        timeframe = item["timeframe"]

        candles = fetch_klines_fn(symbol, timeframe, get_limit_fn(timeframe))
        if not candles:
            still_pending.append(item)
            continue

        idx = None
        for i, c in enumerate(candles):
            if c["close_time"] == item["close_time"]:
                idx = i
                break

        if idx is None:
            still_pending.append(item)
            continue

        max_h = max(item["target_horizons"])
        if idx + max_h >= len(candles):
            still_pending.append(item)
            continue

        entry = item["entry_price"]
        result = {
            "evaluated_at": int(time.time()),
            "id": item["id"],
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": item["strategy"],
            "signal": item["signal"],
            "reason": item["reason"],
            "entry_price": entry,
            "close_time": item["close_time"],
            "outcomes": {}
        }

        for h in item["target_horizons"]:
            future_close = candles[idx + h]["close"]
            change_pct = ((future_close - entry) / entry) * 100.0

            if item["signal"] == "SHORT":
                change_pct = -change_pct

            result["outcomes"][f"{h}_bar"] = {
                "future_close": future_close,
                "pnl_pct": round(change_pct, 4)
            }

        append_jsonl(PERFORMANCE_LOG_PATH, result)

    state["pending_signals"] = still_pending
