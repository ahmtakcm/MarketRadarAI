# MarketRadarAI Runtime Behavior

`main.py` is the daemon entrypoint. It should stay alive under systemd and bootstrap the scanner runtime.

## Ownership

- `main.py`: process entrypoint, logging setup, single-instance guard, graceful shutdown, runtime bootstrap.
- `core.scanner_orchestrator.ScannerRuntime`: scanner loop orchestration, symbol refresh, one-time Telegram command menu sync, `/scan_now` consume, and scan cycle ownership.
- `core.asset_universe`: watchlist-to-source symbol resolution.
- `core.symbol_resolver`: exact/alias symbol interpretation without API calls or guessing.
- `core.symbol_catalog`: read-only symbol metadata enrichment.
- `core.market_data_service`: validated market-data boundary over the current MEXC client.
- `core.scanner`: signal message construction from supported symbols.
- `core.scheduler`: next scan sleep interval.
- `telegram_commands.py`: backward-compatible Telegram runtime facade.
- `telegram/`: dispatcher, handlers, guards, menu sync, messages, and offset persistence.
- `remote_config.py`: mutable runtime config.
- `core.state_store`: runtime scanner state.

## Active Telegram Behavior

Active admin-private commands are:

- `/help`
- `/health`
- `/status`
- `/scan_now`
- `/restart`
- `/modes`
- `/scalp_on`
- `/scalp_off`
- `/filters`
- `/fake_filter_on`
- `/fake_filter_off`
- `/volume_filter_on`
- `/volume_filter_off`
- `/watchlist`
- `/add_symbol`
- `/remove_symbol`
- `/performance_today`
- `/log`
- `/error_log`

Group commands are currently disabled. The command set is unchanged by the asset-universe migration.

## Config And State Boundaries

- Static/local config: `settings.json`.
- Safe example config: `settings.example.json`.
- Mutable runtime/user config: `runtime/remote_config.json`.
- Legacy runtime/user config seed: `remote_config.json`.
- Scanner state: `data/state.json`.
- Signal journals: `data/signal_journal.jsonl`, `data/signals_log.jsonl`, and `data/performance_log.jsonl`.
- Symbol cache: `storage/last_active_symbols.json`.
- Process lock: `storage/alarm_bot.lock`.
- Telegram offset: `telegram_offset.txt`.
- Logs: `logs/app.log` and journald stderr stream.
- Manual backups: `backups/`.

## Runtime Config Write Safety

`runtime/remote_config.json` is the only mutable runtime config target. It is ignored by git and must not be restored from the tracked legacy `remote_config.json` unless a manual recovery explicitly requires it.

Runtime config writes use two layers:

- Atomic write: config is written to a temporary file, flushed, fsynced, then moved into place.
- File lock: read-modify-write updates are serialized through `runtime/remote_config.lock`.

Telegram commands and scanner runtime code must use `remote_config.update_config(mutator)` for read-modify-write changes such as `/scan_now`, mode/filter toggles, and watchlist updates. Direct `load_config() -> mutate -> save_config()` is not safe for concurrent writers.

If the runtime config is corrupt, it is archived as `remote_config.json.broken` and recreated from defaults. Existing schema migration and legacy seeding behavior remain unchanged.

## Loop Model

1. Load state and runtime config.
2. Sync Telegram command menu once and start the Telegram command polling thread.
3. Load active exchange symbols with fallback cache.
4. Resolve watchlist against active exchange symbols.
5. Scan supported symbols for active modes through MarketDataService.
6. Persist state and signal journals.
7. Sleep until the scheduler says to scan again.

`/scan_now` sets `runtime.force_scan_once = true`. The daemon consumes that flag, clears it, and runs the next scan cycle without waiting for the normal sleep to finish.

## Exit Model

- Normal operator shutdown: `KeyboardInterrupt` or systemd stop.
- Duplicate instance: the lock guard exits cleanly and logs the lock path.
- Fatal startup/runtime exception: logged as `MarketRadarAI fatal crash` and re-raised.

The production unit should use `Restart=on-failure`, not `Restart=always`, because this is a daemon rather than a one-shot job.

## Deployment Rules

- Production runs from `main` only.
- Do not work directly on `main`.
- Feature branches are for PR validation only.
- Runtime config must not be committed.
- Service/repo/path rename must follow `docs/DEPLOYMENT.md`; it is operational migration work, not scanner behavior work.

## Deferred Work

- Move Telegram polling ownership out of the scanner process if a dedicated Telegram service is reintroduced.
- Split larger Telegram command families further if the command set grows.
- Add an explicit runtime stop token for graceful thread shutdown and bounded integration tests.
- Introduce a real exchange adapter interface without changing scanner candle contracts.
- Add file locking to scanner state writes if multiple state writers are introduced.
- Apply repository/package path rename only after the service migration checklist is validated.
