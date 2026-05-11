# MarketRadarAI Runtime Behavior

This document records the current behavior before larger MarketRadarAI migrations.
It is intentionally descriptive: it must not be treated as permission to change runtime behavior in the same PR.

## Current Entry Points

- `main.py` starts the long-running scanner process.
- `single_instance.py` prevents duplicate scanner processes through `storage/alarm_bot.lock`.
- `main.py` currently calls Telegram command polling through `poll_telegram_commands`.
- `telegram_commands.py` is the active Telegram command implementation.
- `commands/registry.py` is a passive registry for tooling/tests and must not replace the active dispatcher without a separate migration PR.

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

Group commands are currently disabled.

## Config And State Boundaries

- Static/local config: `settings.json`.
- Safe example config: `settings.example.json`.
- Mutable runtime/user config: `remote_config.json`.
- Scanner state: `data/state.json`.
- Signal journals: `data/signal_journal.jsonl`, `data/signals_log.jsonl`, and `data/performance_log.jsonl`.
- Symbol cache: `storage/last_active_symbols.json`.
- Process lock: `storage/alarm_bot.lock`.
- Telegram offset: `telegram_offset.txt`.
- Logs: `logs/app.log`.

## Deployment Rules

- Production runs from `main` only.
- Do not work directly on `main`.
- Feature branches are for PR validation only.
- Keep hardening PRs small and reversible.
- Do not change Telegram commands, scanner flow, or config values in documentation-only or hardening-only work.

## Deferred Work

These items are intentionally out of scope for this preparation PR:

- Split `telegram_commands.py` into multiple runtime modules.
- Change the active Telegram command dispatcher.
- Move Telegram polling ownership out of `main.py`.
- Introduce a generic exchange adapter interface.
- Rename repository/package paths.
- Stop tracking `remote_config.json` or migrate it to a generated local file.
- Change visible Telegram command text or command names.
- Change scanner scheduling, signal generation, or watchlist semantics.
