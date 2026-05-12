# MarketRadarAI Architecture

MarketRadarAI is a multi-timeframe market scanner with Telegram signal notifications.
This document describes the current architecture and the safe migration direction.

## Folder Structure

- `main.py`: process entry point, logging setup, single-instance guard, and runtime bootstrap.
- `core/scanner_orchestrator.py`: long-running scanner runtime orchestration.
- `core/market_data_service.py`: market-data boundary over the current MEXC client.
- `core/`: symbol resolution, asset universe resolution, exchange access, scanner, scheduler, indicators, signal engine, performance tracking, observability, and state persistence.
- `strategies/`: individual signal strategies used by `core.signal_engine`.
- `telegram/`: active Telegram runtime modules for dispatcher, handlers, guards, menu sync, message formatting, and offsets.
- `telegram_commands.py`: backward-compatible facade for the active Telegram runtime.
- `commands/`: passive command registry used by tooling and tests. It must not replace the active dispatcher without a separate PR.
- `notifiers/` and `services/`: Telegram send wrappers.
- `docs/`: runtime, architecture, and release notes.
- `data/`: runtime state, signal journals, and performance journals.
- `storage/`: process lock and cached exchange symbol data.
- `runtime/`: untracked runtime config target.
- `logs/`: runtime logs.
- `backups/` and `updates/backups/`: operational backups.
- `deploy/systemd/`: repo-managed systemd templates for legacy compatibility and MarketRadarAI target service.

## Main Flow

1. `main.py` loads runtime/user config for startup metadata.
2. It logs startup visibility: exchange, active modes, watchlist count, state path, and runtime config path.
3. It creates `core.scanner_orchestrator.ScannerRuntime`.
4. `ScannerRuntime` loads scanner state through `core.state_store.load_state`.
5. It syncs the Telegram command menu once, then starts Telegram command polling in-process.
6. It discovers MEXC futures symbols and resolves the watchlist through `core.asset_universe`.
7. It scans active mode plans on candle-close scheduling.
8. It sends Telegram notifications for new signal messages.
9. It writes state and journals.
10. It is intended to stay alive as a daemon. A normal return from `main.py` is not the expected
   service lifecycle.

## Telegram Flow

- `telegram_commands.py` remains the active import facade.
- `telegram/dispatcher.py` owns polling.
- `telegram/handlers.py` owns command execution.
- `telegram/guards.py` owns authorization and command-set constants.
- `telegram/menu.py` owns command menu sync.
- `telegram/messages.py` owns user-visible command text.
- `core.scanner_orchestrator.ScannerRuntime` owns one-time command menu sync.
- Admin-private commands are the current production command set.
- Group commands are currently disabled through `GROUP_SAFE_COMMANDS = set()`.
- `/scan_now` sets `runtime.force_scan_once = true`.
- `ScannerRuntime.sleep_with_command_polling` exits sleep early when that flag is visible.
- `ScannerRuntime.consume_force_scan_request` clears the flag before the next scanner iteration.

## Scanner Flow

- `core.asset_universe` separates requested watchlist entries from symbols supported by the active source.
- `core.scanner_orchestrator.ScannerRuntime` owns symbol refresh, force-scan consume, scan-cycle logging, and loop error isolation.
- `core.scheduler` chooses active mode plans from `remote_config`.
- `core.scanner` fetches entry/setup/bias candles, builds levels, runs strategies, applies MTF filters, and registers pending performance tracking.
- `core.performance_tracker` finalizes signal outcomes after configured future bar horizons.
- Scanner semantics are intentionally unchanged in this PR.

## State Flow

- `data/state.json` is runtime state.
- It now has `schema_version`.
- `core.state_store` loads legacy state without schema version, migrates it in memory, and writes atomically.
- Corrupt state is moved to `state.json.broken`; a safe default state is recreated.

## Config Flow

- `settings.json` is local static config and may contain Telegram credentials.
- `settings.example.json` is the tracked safe template.
- `remote_config.example.json` is the tracked safe template for runtime/user config.
- `remote_config.json` remains a legacy tracked seed for backward compatibility.
- New runtime writes go to `runtime/remote_config.json` by default.
- `MARKETRADAR_RUNTIME_CONFIG` can override the runtime config path.
- If `runtime/remote_config.json` does not exist but legacy `remote_config.json` exists, the legacy file is copied into runtime config first. This preserves production overrides such as `modes.scalp = true`.
- Runtime config writes are atomic and protected by `runtime/remote_config.lock`.
- Read-modify-write paths must use `remote_config.update_config(mutator)` so Telegram commands and scanner runtime flag consumption do not overwrite each other.

## Exchange Flow

- `core.exchange_client` is the current MEXC market-data client.
- `core.market_data_service` is the boundary consumed by scanner runtime and scanner code.
- It converts plain symbols to MEXC contract symbols.
- It normalizes kline rows into scanner candle dictionaries.
- `core.symbol_resolver` is the single symbol interpretation layer for exact matches and explicit aliases.
- `core.asset_universe` treats MEXC as the active crypto-futures source and exposes unsupported watchlist entries instead of silently dropping them.
- `core.symbol_catalog` is read-only enrichment metadata and does not route or validate symbols.
- MarketDataService accepts already-resolved uppercase exchange symbols; it does not alias, guess, or normalize user input.
- Multi-exchange adapters are deferred.

## Signal Flow

- `core.signal_engine` runs configured strategy modules.
- `core.mtf_signal_engine` applies MTF alignment, fake breakout, and volume filters.
- `signal_journal.py` stores signal journal artifacts under `data/`.
- `core.performance_tracker` writes performance results under `data/`.

## Runtime Persistence Inventory

| Path | Class | Notes |
| --- | --- | --- |
| `settings.json` | user config | Local credentials and static settings; ignored by git. |
| `settings.example.json` | default config | Safe tracked template. |
| `remote_config.example.json` | default config | Safe tracked runtime config template. |
| `remote_config.json` | legacy default/seed config | Backward-compatible seed only; runtime writes move to `runtime/remote_config.json`. |
| `runtime/remote_config.json` | user config/runtime control | Mutable Telegram/scanner control config; ignored by git. |
| `data/state.json` | runtime state | Scanner memory, dedupe state, pending signals; atomic write and recovery. |
| `telegram_offset.txt` | runtime state | Telegram update offset; ignored by git. |
| `storage/alarm_bot.lock` | runtime state | Single-process lock. |
| `storage/last_active_symbols.json` | cache | Exchange symbol cache. |
| `data/signal_journal.jsonl` | audit/log | Signal journal. |
| `data/signals_log.jsonl` | audit/log | Structured signal log. |
| `data/performance_log.jsonl` | audit/log | Signal outcome log. |
| `data/last_signal.txt` | generated artifact | Last signal snapshot. |
| `logs/app.log` | log | Runtime application log. |
| `backups/` | backup | Manual/operational backups; ignored by git. |
| `updates/backups/` | backup | Update manager backups; runtime artifact. |

## Dirty State Analysis

In this local workspace, `remote_config.json` was clean when this PR started on `feature/runtime-state-hardening`, and `backups/` was not present.
The reported server state can still happen in production because the active runtime path was previously the tracked `remote_config.json`.
Key-order or formatting changes can occur whenever `save_config` rewrites JSON.
Real production overrides are values such as `modes.scalp = true`, watchlist values, filters, limits, and runtime flags.

This PR preserves production overrides by seeding `runtime/remote_config.json` from the existing legacy `remote_config.json` on first run, then writing only to the untracked runtime path.

## Production Risk Assessment

Most critical production risks:

- Systemd may be configured to restart clean exits, hiding duplicate-instance or wrong-entrypoint loops.
- File-only logging can make the application appear silent in `journalctl`.
- Mutable runtime config was tracked by git.
- Runtime config writes could leave the working tree dirty.
- State writes were non-atomic.
- Corrupt state/config recovery was implicit and not visible.
- Telegram polling currently runs inside the scanner process; ownership is explicit in `ScannerRuntime`, but a dedicated poller remains a future risk.
- Command authorization uses hardcoded chat IDs and must remain stable until a dedicated migration.

Most risky runtime files:

- `runtime/remote_config.json`
- `runtime/remote_config.lock`
- `data/state.json`
- `telegram_offset.txt`
- `storage/alarm_bot.lock`
- `data/*jsonl`

Most risky race conditions:

- Telegram commands and scanner both load/save runtime config.
- Runtime config updates are serialized by a lock, but callers must keep using `update_config` for read-modify-write changes.
- Scanner writes state while a process exits unexpectedly.
- Multiple in-process Telegram polling paths rely on a process-local lock; command menu sync is no longer part of each polling call.

Most risky recovery scenarios:

- Corrupt `remote_config.json` or `runtime/remote_config.json`.
- Corrupt `data/state.json`.
- Lost `telegram_offset.txt` causing old Telegram updates to be reprocessed.
- Accidental rollback from stale backups.

Most risky Telegram command surfaces:

- `/restart`
- `/scan_now`
- `/add_symbol`
- `/remove_symbol`
- filter and mode toggles

Risks reduced in this PR:

- Application logs now go to both `logs/app.log` and stderr for journald visibility.
- Duplicate-instance clean exits are logged before the process exits.
- Deployment docs now recommend `Restart=on-failure` for the long-running daemon model.
- Runtime config writes no longer target the tracked config file.
- Runtime config and scanner state have schema version fields.
- Runtime config and scanner state use atomic writes.
- Corrupt runtime config and scanner state get safe fallback recovery.
- Startup logs expose active exchange, modes, watchlist count, and persistence paths.
- Asset universe logs expose requested, supported, and unsupported watchlist counts.
- Telegram command menu sync has a single runtime owner instead of being coupled to every polling call.
- Scan loop logs expose start/finish, active modes, symbol count, and duration without changing scanner behavior.
- Passive command registry and active dispatcher command set are tested.

Deferred risks:

- Move Telegram polling ownership out of the scanner process if a dedicated Telegram service is reintroduced.
- Add a repo-managed systemd unit once production unit contents are confirmed.
- Add file locking to scanner state writes if future architecture introduces multiple state writers.
- Move hardcoded Telegram chat IDs into local config without changing behavior.
- Split larger Telegram command families further if command volume grows.
- Introduce a MEXC adapter interface without changing scanner candle contracts.
- Apply the prepared service/repo/path rename checklist from `docs/DEPLOYMENT.md`.

## Safe Target Structure

Future PRs can move toward:

- `config/`: default schemas, local settings loaders, runtime config loader.
- `runtime/`: runtime persistence helpers and file locking.
- `commands/`: command definitions and handler mapping.

Migration must stay incremental. Keep the active Telegram dispatcher and scanner contracts stable until each slice has tests and live validation.
