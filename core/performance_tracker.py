import time
from pathlib import Path

from core.signal_lifecycle import build_pending_signal_record, build_signal_dedupe_key
from core.state_store import append_jsonl

try:
    from config import PERFORMANCE_LOG_PATH, SIGNAL_HORIZONS_BARS
except Exception:
    BASE_DIR = Path(__file__).resolve().parents[1]
    PERFORMANCE_LOG_PATH = BASE_DIR / "data" / "performance_log.jsonl"
    SIGNAL_HORIZONS_BARS = [1, 3, 5]


def register_signal(
    state,
    symbol,
    timeframe,
    strategy_name,
    signal,
    reason,
    levels,
    *,
    stop_loss=None,
    take_profit_levels=None,
):
    signal_id = build_signal_dedupe_key(symbol, timeframe, strategy_name, levels["close_time"], signal)

    for item in state.get("pending_signals", []):
        if item["id"] == signal_id:
            return

    row = build_pending_signal_record(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy_name,
        signal=signal,
        reason=reason,
        levels=levels,
        target_horizons=SIGNAL_HORIZONS_BARS,
        timestamp=int(time.time()),
        stop_loss=stop_loss,
        take_profit_levels=take_profit_levels,
    )

    state.setdefault("pending_signals", []).append(row)


def _tp_sl_outcome(item, future_candles):
    signal = item.get("signal")
    stop_loss = item.get("stop_loss")
    take_profit_levels = item.get("take_profit_levels") or []

    if signal not in {"LONG", "SHORT"} or stop_loss is None or not take_profit_levels:
        return {
            "status": "NOT_TRACKED",
            "reason": "tp/sl levels missing",
        }

    for offset, candle in enumerate(future_candles, start=1):
        high = candle.get("high")
        low = candle.get("low")
        close_time = candle.get("close_time")
        if high is None or low is None:
            continue

        if signal == "LONG":
            sl_hit = low <= stop_loss
            hit_tps = [tp for tp in take_profit_levels if high >= tp]
        else:
            sl_hit = high >= stop_loss
            hit_tps = [tp for tp in take_profit_levels if low <= tp]

        if sl_hit and hit_tps:
            return {
                "status": "BOTH_HIT_SAME_BAR",
                "bar_offset": offset,
                "close_time": close_time,
                "stop_loss": stop_loss,
                "take_profit": hit_tps[-1],
                "tp_index": len(hit_tps),
            }

        if sl_hit:
            return {
                "status": "SL_HIT",
                "bar_offset": offset,
                "close_time": close_time,
                "stop_loss": stop_loss,
            }

        if hit_tps:
            return {
                "status": "TP_HIT",
                "bar_offset": offset,
                "close_time": close_time,
                "take_profit": hit_tps[-1],
                "tp_index": len(hit_tps),
            }

    return {
        "status": "OPEN",
        "checked_bars": len(future_candles),
    }


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
            "stop_loss": item.get("stop_loss"),
            "take_profit_levels": item.get("take_profit_levels", []),
            "close_time": item["close_time"],
            "tp_sl_outcome": _tp_sl_outcome(item, candles[idx + 1 : idx + max_h + 1]),
            "outcomes": {},
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
