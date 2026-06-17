from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SignalLifecycleCandidate:
    symbol: str
    timeframe: str
    strategy: str
    signal: str
    reason: str
    entry_price: float
    close_time: int
    target_horizons: list[int]
    stop_loss: float | None = None
    take_profit_levels: list[float] | None = None


def build_signal_dedupe_key(
    symbol: str,
    timeframe: str,
    strategy: str,
    close_time: int,
    signal: str,
) -> str:
    return f"{symbol}_{timeframe}_{strategy}_{close_time}_{signal}"


def build_pending_signal_record(
    *,
    symbol: str,
    timeframe: str,
    strategy: str,
    signal: str,
    reason: str,
    levels: dict[str, Any],
    target_horizons: list[int],
    timestamp: int | None = None,
    stop_loss: float | None = None,
    take_profit_levels: list[float] | None = None,
) -> dict[str, Any]:
    candidate = SignalLifecycleCandidate(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        signal=signal,
        reason=reason,
        entry_price=levels["close"],
        close_time=levels["close_time"],
        target_horizons=list(target_horizons),
        stop_loss=stop_loss,
        take_profit_levels=list(take_profit_levels or []),
    )
    signal_id = build_signal_dedupe_key(
        candidate.symbol,
        candidate.timeframe,
        candidate.strategy,
        candidate.close_time,
        candidate.signal,
    )
    record = {
        "timestamp": int(time.time()) if timestamp is None else int(timestamp),
        "id": signal_id,
        "symbol": candidate.symbol,
        "timeframe": candidate.timeframe,
        "strategy": candidate.strategy,
        "signal": candidate.signal,
        "reason": candidate.reason,
        "entry_price": candidate.entry_price,
        "close_time": candidate.close_time,
        "target_horizons": candidate.target_horizons,
    }
    if candidate.stop_loss is not None:
        record["stop_loss"] = candidate.stop_loss
    if candidate.take_profit_levels:
        record["take_profit_levels"] = candidate.take_profit_levels
    return record
