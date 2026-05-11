# MarketRadarAI Architecture

MarketRadarAI is a multi-timeframe market scanner with Telegram signal notifications.
This document describes the current architecture and the safe migration direction.

## Folder Structure

- `main.py`: long-running scanner entry point.
- `core/`: exchange access, scanner, scheduler, indicators, signal engine, performance tracking, and state persistence.
- `strategies/`: individual signal strategies used by `core.signal_engine`.
- `telegram_commands.py`: active Telegram command dispatcher and Telegram polling implementation.
- `commands/`: passive command registry used by tooling and tests. It must not replace the active dispatcher without a separate PR.
- `notifiers/` and `services/`: Telegram send wrappers.
- `docs/`: runtime, architecture, and release notes.
- `data/`: runtime state, signal journals, and performance journals.
- `storage/`: process lock and cached exchange symbol data.
- `runtime/`: untracked runtime config target.
- `logs/`: runtime logs.
- `backups/` and `updates/backups/`: operational backups.

## Main Flow

1. `main.py` loads scanner state through `core.state_store.load_state`.
2. It loads runtime/user config through `remote_config.load_config`.
3. It logs startup visibility: exchange, active modes, watchlist count, state path, and runtime config path.
4. It starts Telegram command polling in-process.
5. It discovers MEXC futures symbols and applies the watchlist filter.
6. It scans active mode plans on candle-close scheduling.
7. It sends Telegram notifications for new signal messages.
8. It writes state and journals.

## Telegram Flow

- `telegram_commands.py` is the active dispatcher.
- Admin-private commands are the current production command set.
- Group commands are currently disabled through `GROUP_SAFE_COMMANDS = set()`.
- `/scan_now` sets `runtime.force_scan_once = true`.
- `main.sleep_with_command_polling` exits sleep early when that flag is visible.
- `main.consume_force_scan_request` clears the flag before the next scanner iteration.

## Scanner Flow

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

## Exchange Flow

- `core.exchange_client` is the current MEXC market-data client.
- It converts plain symbols to MEXC contract symbols.
- It normalizes kline rows into scanner candle dictionaries.
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

- Mutable runtime config was tracked by git.
- Runtime config writes could leave the working tree dirty.
- State writes were non-atomic.
- Corrupt state/config recovery was implicit and not visible.
- Telegram polling currently runs inside `main.py`; ownership is still a future risk.
- Command authorization uses hardcoded chat IDs and must remain stable until a dedicated migration.

Most risky runtime files:

- `runtime/remote_config.json`
- `data/state.json`
- `telegram_offset.txt`
- `storage/alarm_bot.lock`
- `data/*jsonl`

Most risky race conditions:

- Telegram commands and scanner both load/save runtime config.
- Scanner writes state while a process exits unexpectedly.
- Multiple in-process Telegram polling paths rely on a process-local lock.

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

- Runtime config writes no longer target the tracked config file.
- Runtime config and scanner state have schema version fields.
- Runtime config and scanner state use atomic writes.
- Corrupt runtime config and scanner state get safe fallback recovery.
- Startup logs expose active exchange, modes, watchlist count, and persistence paths.
- Passive command registry and active dispatcher command set are tested.

Deferred risks:

- Move Telegram polling ownership out of `main.py`.
- Add file locking or compare-and-swap for runtime config writes.
- Move hardcoded Telegram chat IDs into local config without changing behavior.
- Split `telegram_commands.py` safely.
- Introduce a MEXC adapter interface without changing scanner candle contracts.

## Safe Target Structure

Future PRs can move toward:

- `config/`: default schemas, local settings loaders, runtime config loader.
- `runtime/`: runtime persistence helpers and file locking.
- `commands/`: command definitions and handler mapping.

Migration must stay incremental. Keep the active Telegram dispatcher and scanner contracts stable until each slice has tests and live validation.
