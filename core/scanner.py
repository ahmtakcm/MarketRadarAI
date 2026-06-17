import logging
import time
from pathlib import Path

from core.indicator_engine import build_levels
from core.market_data_service import (
    DEFAULT_MARKET_DATA_SERVICE,
    MarketDataService,
)
from core.mtf_signal_engine import analyze_mtf_signal
from core.state_store import append_jsonl
from macro_bridge import get_macro_signal, macro_direction_for_symbol
from remote_config import load_config

BASE_DIR = Path(__file__).resolve().parents[1]


def _service(market_data_service: MarketDataService | None = None) -> MarketDataService:
    return market_data_service or DEFAULT_MARKET_DATA_SERVICE


def _signals_log_path():
    try:
        from config import SIGNALS_LOG_PATH

        return SIGNALS_LOG_PATH
    except Exception:
        return BASE_DIR / "data" / "signals_log.jsonl"


def _commentary_symbols() -> set[str]:
    try:
        from config import COMMENTARY_SYMBOLS

        return set(COMMENTARY_SYMBOLS)
    except Exception:
        return set()


def _active_mode_plans():
    from core.scheduler import get_active_mode_plans

    return get_active_mode_plans()


def _generate_signals(context):
    from core.signal_engine import generate_signals

    return generate_signals(context)


def _build_daily_commentary(symbol, levels):
    from core.signal_engine import build_daily_commentary

    return build_daily_commentary(symbol, levels)


def _phase_alert_allowed(state, key, current_close, cooldown_candles=4):
    alerts = state.setdefault("last_phase_alerts", {})
    record = alerts.get(key)
    if not isinstance(record, dict):
        record = {}

    if record.get("last_seen_close") == current_close:
        return False

    seen_count = int(record.get("seen_count", 0)) + 1
    last_alert_seen_count = int(record.get("last_alert_seen_count", 0))
    should_alert = not record or seen_count - last_alert_seen_count >= cooldown_candles

    updated = {
        "last_seen_close": current_close,
        "seen_count": seen_count,
        "last_alert_seen_count": last_alert_seen_count,
        "last_alert_close": record.get("last_alert_close"),
    }
    if should_alert:
        updated["last_alert_seen_count"] = seen_count
        updated["last_alert_close"] = current_close

    alerts[key] = updated
    return should_alert


def _register_signal(state, symbol, timeframe, strategy_name, signal, reason, levels):
    from core.performance_tracker import register_signal

    register_signal(state, symbol, timeframe, strategy_name, signal, reason, levels)


def _valid_stop_loss(direction, entry_price, stop_loss):
    if direction == "LONG":
        return stop_loss < entry_price
    if direction == "SHORT":
        return stop_loss > entry_price
    return True


def _profit_targets(direction, entry_price, levels):
    if direction == "LONG":
        keys = ["upper_fib1", "upper_fib2", "upper_fib3", "upper_fib4", "upper_fib5"]
        return [levels.get(key) for key in keys if levels.get(key) is not None and levels.get(key) > entry_price]

    if direction == "SHORT":
        keys = ["lower_fib1", "lower_fib2", "lower_fib3", "lower_fib4", "lower_fib5"]
        return [levels.get(key) for key in keys if levels.get(key) is not None and levels.get(key) < entry_price]

    return []


def get_active_symbols(market_data_service: MarketDataService | None = None):
    """
    Borsadaki geçerli futures sembollerini döndürür.
    High alert sembol listesini daraltmaz; sadece mesaj/öncelik katmanı olarak kullanılır.
    """
    return _service(market_data_service).get_valid_futures_symbols()


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
    append_jsonl(_signals_log_path(), row)


def _fetch_context(symbol, tf, market_data_service: MarketDataService | None = None):
    service = _service(market_data_service)
    candles = service.fetch_klines(symbol, tf, service.get_kline_limit(tf))
    if not candles:
        return None, None

    levels = build_levels(candles)
    if not levels:
        return candles, None

    return candles, levels


def _bias_text(entry_signal, bias_levels, setup_levels, plan):
    bias_tf = plan["bias"]
    setup_tf = plan["setup"]
    entry_tf = plan["entry"]

    bias_close = bias_levels.get("close") if bias_levels else None
    bias_center = bias_levels.get("center") if bias_levels else None
    setup_close = setup_levels.get("close") if setup_levels else None
    setup_center = setup_levels.get("center") if setup_levels else None

    bias_side = "nötr"
    setup_side = "nötr"

    if bias_close is not None and bias_center is not None:
        bias_side = "yukarı" if bias_close >= bias_center else "aşağı"

    if setup_close is not None and setup_center is not None:
        setup_side = "yukarı" if setup_close >= setup_center else "aşağı"

    return (
        f"Mod: {plan['label']} ({plan['mode']})\n"
        f"Zaman Yapısı: Bias {bias_tf} | Setup {setup_tf} | Entry {entry_tf}\n"
        f"Bias Durumu: {bias_tf} {bias_side}\n"
        f"Setup Durumu: {setup_tf} {setup_side}"
    )


def build_signal_lines(symbols, state, market_data_service: MarketDataService | None = None):
    lines = []
    plans = _active_mode_plans()
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

                entry_candles, entry_levels = _fetch_context(symbol, entry_tf, market_data_service)
                if not entry_levels:
                    continue

                close_key = f"{symbol}_{mode}_{entry_tf}"
                last_saved_close = state["last_processed_close_times"].get(close_key)
                current_close = entry_levels["close_time"]

                if last_saved_close == current_close:
                    continue

                _bias_candles, bias_levels = _fetch_context(symbol, bias_tf, market_data_service)
                _setup_candles, setup_levels = _fetch_context(symbol, setup_tf, market_data_service)

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

                signals = _generate_signals(strategy_context)
                state["last_processed_close_times"][close_key] = current_close

                for sig in signals:
                    signal = sig["signal"]
                    reason = sig["reason"]
                    strategy_name = sig["strategy"]
                    reason_clean = str(reason or "").replace("FiBB Bands: ", "").strip()

                    if sig.get("candidate_type") == "phase":
                        phase_key = f"{symbol}:{mode}:{entry_tf}:{signal}"
                        if not _phase_alert_allowed(state, phase_key, current_close):
                            continue

                        quality = sig.get("quality", "WATCH")
                        score_text = f" {sig['score']}/100" if sig.get("score") is not None else ""
                        message_block = (
                            f"⚠ {strategy_name}\n\n"
                            f"{symbol} ({plan['label']} - {entry_tf.upper()}) → {signal} | {quality}{score_text}\n\n"
                            f"Neden:\n{reason_clean}"
                        )
                        results.append(message_block)
                        continue

                    mtf = analyze_mtf_signal(sig, bias_levels, setup_levels, entry_levels, plan, cfg)
                    if not mtf["allowed"]:
                        continue

                    price = entry_levels["close"]
                    center = entry_levels["center"]
                    stop_loss = sig.get("stop_loss", center)

                    direction = "LONG" if "LONG" in signal else "SHORT" if "SHORT" in signal else signal

                    if not _valid_stop_loss(direction, price, stop_loss):
                        logging.warning(
                            "Trade sinyali atlandi: stop loss entry yonune gore gecersiz | %s %s %s entry=%s sl=%s",
                            symbol,
                            entry_tf,
                            direction,
                            price,
                            stop_loss,
                        )
                        continue

                    tp_levels = _profit_targets(direction, price, entry_levels)
                    if direction in {"LONG", "SHORT"} and not tp_levels:
                        logging.warning(
                            "Trade sinyali atlandi: entry yonunde kar hedefi yok | %s %s %s entry=%s",
                            symbol,
                            entry_tf,
                            direction,
                            price,
                        )
                        continue

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
                        f"🚨 {strategy_name}\n\n"
                        f"{symbol} ({plan['label']} - {entry_tf.upper()}) → {direction} | {sig.get('quality', mtf['quality'])} {sig.get('score', mtf['score'])}/100\n\n"
                        f"Neden:\n{reason_clean}\n\n"
                        f"Seviyeler:\n"
                        f"Entry: {price:.2f}\n"
                        f"SL: {stop_loss:.2f}\n"
                        f"{tp_text.rstrip()}{macro_text}"
                    )

                    results.append(message_block)
                    log_signal(symbol, entry_tf, strategy_name, signal, reason, entry_levels, mode=mode)
                    _register_signal(state, symbol, entry_tf, strategy_name, signal, reason, entry_levels)

            if results:
                block = f"{symbol}\n" + "\n".join(results)
                lines.append(block)

        except Exception as e:
            logging.exception("Sembol tarama hatası; sembol atlandı | %s | %s", symbol, e)
            continue

    return lines



def build_signal_message(symbols, state, market_data_service: MarketDataService | None = None):
    lines = build_signal_lines(symbols, state, market_data_service)
    if not lines:
        return None

    return "🚨 SİNYAL\n\n" + "\n\n".join(lines)


def get_daily_commentaries(symbols, state, market_data_service: MarketDataService | None = None):
    comments = []
    state.setdefault("daily_commentary", {})
    commentary_symbols = _commentary_symbols()

    for symbol in symbols:
        if symbol not in commentary_symbols:
            continue

        service = _service(market_data_service)
        candles = service.fetch_klines(symbol, "1d", service.get_kline_limit("1d"))
        if not candles:
            continue

        levels = build_levels(candles)
        if not levels:
            continue

        close_time = levels["close_time"]
        if state["daily_commentary"].get(symbol) == close_time:
            continue

        comments.append(_build_daily_commentary(symbol, levels))
        state["daily_commentary"][symbol] = close_time

    return comments
