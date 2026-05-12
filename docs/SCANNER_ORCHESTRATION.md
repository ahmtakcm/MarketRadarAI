# MarketRadarAI Scanner Orchestration

`main.py` is now the process entrypoint. Scanner runtime behavior lives in `core.scanner_orchestrator.ScannerRuntime`.

## `main.py` Responsibilities

- Configure application logging for file and journald output.
- Emit startup metadata.
- Send the minimal lifecycle startup notification.
- Create `ScannerRuntime`.
- Run under the single-instance lock.
- Log graceful shutdown and fatal crash paths.

## `ScannerRuntime` Responsibilities

- Start and supervise the in-process Telegram polling thread.
- Load active exchange symbols with retry and fallback cache.
- Refresh the active symbol universe on the configured interval.
- Resolve the runtime watchlist through `core.asset_universe`.
- Consume `/scan_now` by clearing `runtime.force_scan_once`.
- Run scan cycles against supported symbols.
- Log scan start/finish metadata.
- Send signal and commentary messages through the injected Telegram sender.
- Persist scanner state through `core.state_store`.
- Isolate main loop exceptions so one failed cycle does not stop the daemon.

## Preserved Behavior

- Telegram command names and authorization rules are unchanged.
- `/scan_now` still sets `runtime.force_scan_once = true`; the runtime clears it before the next scan cycle.
- Scanner strategy logic remains in `core.scanner` and related strategy modules.
- Exchange behavior remains in `core.exchange_client`.
- Runtime config remains `runtime/remote_config.json`.

## Deferred Work

- Move Telegram polling ownership to a single dedicated runtime owner.
- Add explicit stop tokens for controlled tests and graceful thread shutdown.
- Add compare-and-swap or file locking for runtime config writes.
- Split signal delivery audit from strategy scoring.
