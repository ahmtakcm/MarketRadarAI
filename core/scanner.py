import time
import logging

from config import REQUESTED_SYMBOLS, COMMENTARY_SYMBOLS, SIGNALS_LOG_PATH
from core.exchange_client import get_kline_limit, fetch_klines
from macro_bridge import macro_direction_for_symbol, get_macro_signal
from high_alert_bridge import is_high_alert, get_high_alert_assets
from core.indicator_engine import build_levels
from core.signal_engine import generate_signals, build_daily_commentary
from core.performance_tracker import register_signal
from core.state_store import append_jsonl
from core.scheduler import get_active_mode_plans
from remote_config import load_config
from core.mtf_signal_engine import analyze_mtf_signal, build_mtf_context


def _safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        symbol = str(value or "").upper().strip()
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def get_active_symbols():
    cfg = load_config()
    symbols = _safe_symbols(cfg.get("watchlist", {}).get("symbols", []))
    if symbols:
        return symbols

    symbols = _safe_symbols(REQUESTED_SYMBOLS)
    if symbols:
        return symbols

    return ["BTCUSDT", "ETHUSDT"]


def log_signal(symbol, timeframe, strategy_name, signal, reason, levels, mode=None):
    row = {
        "timestamp": int(time.time()),
        "symbol": symbol,
        "mode": mode,
        "timeframe": timeframe,
        "strategy": strategy_name,
        "signal": signal,
        "reason": reason,
        "entry_price": levels["close"],
        "center": levels["center"],
        "close_time": levels["close_time"],
    }
    append_jsonl(SIGNALS_LOG_PATH, row)


def _fetch_context(symbol, tf):
    candles = fetch_klines(symbol, tf, get_kline_limit(tf))
    if not candles:
        return None, None

    levels = build_levels(candles)
    if not levels:
        return candles, None

    return candles, levels


def build_signal_lines(symbols, state):
    lines = []
    plans = get_active_mode_plans()
    cfg = load_config()

    if not plans:
        return lines

    state.setdefault("last_processed_close_times", {})

    for symbol in symbols:
        try:
            results = []

            for plan in plans:
                mode = plan["mode"]
                entry_tf = plan["entry"]
                setup_tf = plan["setup"]
                bias_tf = plan["bias"]

                entry_candles, entry_levels = _fetch_context(symbol, entry_tf)
                if not entry_levels:
                    continue

                close_key = f"{symbol}_{mode}_{entry_tf}"
                last_saved_close = state["last_processed_close_times"].get(close_key)
                current_close = entry_levels["close_time"]

                if last_saved_close == current_close:
                    continue

                _bias_candles, bias_levels = _fetch_context(symbol, bias_tf)
                _setup_candles, setup_levels = _fetch_context(symbol, setup_tf)

                strategy_context = {
                    "symbol": symbol,
                    "mode": mode,
                    "plan": plan,
                    "timeframe": entry_tf,
                    "candles": entry_candles,
                    "levels": entry_levels,
                    "bias_levels": bias_levels,
                    "setup_levels": setup_levels,
                    "indicator_cache": {},
                }

                signals = generate_signals(strategy_context)
                state["last_processed_close_times"][close_key] = current_close

                for sig in signals:
                    mtf = analyze_mtf_signal(sig, bias_levels, setup_levels, entry_levels, plan, cfg)
                    if not mtf["allowed"]:
                        continue

                    signal = sig["signal"]
                    reason = sig["reason"]
                    strategy_name = sig["strategy"]

                    price = entry_levels["close"]
                    center = entry_levels["center"]
                    direction = "LONG" if "LONG" in signal else "SHORT" if "SHORT" in signal else signal

                    if direction == "LONG":
                        tp_levels = [
                            entry_levels.get("upper_fib1"),
                            entry_levels.get("upper_fib2"),
                            entry_levels.get("upper_fib3"),
                            entry_levels.get("upper_fib4"),
                            entry_levels.get("upper_fib5"),
                        ]
                    elif direction == "SHORT":
                        tp_levels = [
                            entry_levels.get("lower_fib1"),
                            entry_levels.get("lower_fib2"),
                            entry_levels.get("lower_fib3"),
                            entry_levels.get("lower_fib4"),
                            entry_levels.get("lower_fib5"),
                        ]
                    else:
                        tp_levels = []

                    reason_clean = str(reason or "").replace("FiBB Bands: ", "").strip()

                    macro_text = ""
                    macro_dir = macro_direction_for_symbol(symbol)
                    macro_signal = get_macro_signal()
                    if macro_dir:
                        if (direction == "LONG" and macro_dir == "bullish") or (direction == "SHORT" and macro_dir == "bearish"):
                            macro_status = "OK Makro teyit var"
                        elif (direction == "LONG" and macro_dir == "bearish") or (direction == "SHORT" and macro_dir == "bullish"):
                            macro_status = "UYARI Makro celiski var"
                        else:
                            macro_status = "BILGI Makro notr/karma"
                        macro_text = (
                            "\\n\\nMakro Kopru:\\n"
                            + macro_status + "\\n"
                            + "Makro yon: " + str(macro_dir) + "\\n"
                            + "Kaynak: " + str(macro_signal.get("source") or "-") + "\\n"
                            + "Olay: " + str(macro_signal.get("event") or "-")
                        )

                    tp_text = ""
                    for i, tp in enumerate(tp_levels, start=1):
                        if tp is not None:
                            tp_text += f"TP{i}: {tp:.2f}\n"

                    message_block = (
                        f"{strategy_name}\n\n"
                        f"{symbol} ({plan['label']} - {entry_tf.upper()}) -> {direction} | {mtf['quality']} {mtf['score']}/100\n\n"
                        f"Neden:\n{reason_clean}\n\n"
                        f"Seviyeler:\n"
                        f"Entry: {price:.2f}\n"
                        f"SL: {center:.2f}\n"
                        f"{tp_text.rstrip()}{macro_text}"
                    )

                    results.append(message_block)
                    log_signal(symbol, entry_tf, strategy_name, signal, reason, entry_levels, mode=mode)
                    register_signal(state, symbol, entry_tf, strategy_name, signal, reason, entry_levels)

            if results:
                block = f"{symbol}\n" + "\n".join(results)
                lines.append(block)

        except Exception as e:
            logging.exception("Sembol tarama hatasi; sembol atlandi | %s | %s", symbol, e)
            continue

    return lines


def build_signal_message(symbols, state):
    lines = build_signal_lines(symbols, state)
    if not lines:
        return None

    return "SINYAL\n\n" + "\n\n".join(lines)


def get_daily_commentaries(symbols, state):
    comments = []
    state.setdefault("daily_commentary", {})

    for symbol in symbols:
        if symbol not in COMMENTARY_SYMBOLS:
            continue

        candles = fetch_klines(symbol, "1d", get_kline_limit("1d"))
        if not candles:
            continue

        levels = build_levels(candles)
        if not levels:
            continue

        close_time = levels["close_time"]
        if state["daily_commentary"].get(symbol) == close_time:
            continue

        comments.append(build_daily_commentary(symbol, levels))
        state["daily_commentary"][symbol] = close_time

    return comments
