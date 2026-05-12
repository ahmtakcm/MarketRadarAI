# MarketRadarAI Signal Lifecycle

This document describes the current signal contract. It is intentionally not a new signal engine.

## Current Flow

1. Asset universe resolution selects supported symbols for the active source.
2. `core.scanner.build_signal_message` scans those symbols.
3. Strategy modules produce candidates through the existing scanner/signal-engine path.
4. Scanner output is rendered as a Telegram-ready signal message.
5. Duplicate suppression compares the new message with `state["last_sent_message"]`.
6. New messages are written through `signal_journal.py`.
7. Telegram delivery happens unless quiet mode is enabled.
8. `core.performance_tracker.finalize_pending_signals` records later outcomes.
9. `core.state_store.save_state` persists runtime state atomically.

## Contract

The current contract is:

`candidate -> score/filter -> signal message -> delivery/audit -> state update -> recovery`

- Candidate: strategy modules evaluate scanner context and may return a signal.
- Score/filter: `core.mtf_signal_engine` applies multi-timeframe quality, fake-breakout, and volume filters.
- Signal message: `core.scanner` formats the currently delivered Telegram message.
- Delivery/audit: `ScannerRuntime` writes signal journals before Telegram delivery.
- Cooldown/state: current duplicate suppression is message-level through `state["last_sent_message"]`; pending performance items are stored in state.
- Recovery: `core.state_store` migrates legacy state, recovers corrupt state, and persists atomically.

Scanner and Telegram boundaries must stay separate: scanner creates signal content, while Telegram runtime only delivers command replies and outbound notifications passed by the scanner runtime.

## Current Persistence

- Last delivered message: `data/state.json`
- Signal journal: `data/signal_journal.jsonl`
- Structured signal log: `data/signals_log.jsonl`
- Performance journal: `data/performance_log.jsonl`
- Last signal snapshot: `data/last_signal.txt`

## Deferred Contract Work

- Add an explicit candidate object before Telegram rendering.
- Add a stable dedupe key such as `symbol + mode + timeframe + close_time + strategy + direction`.
- Split delivery audit from strategy scoring.
- Add restart recovery tests for pending signal performance tracking.
