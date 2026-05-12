# MarketRadarAI Telegram Runtime

Telegram runtime behavior remains backward compatible with the previous `telegram_commands.py` surface.
`telegram_commands.py` is now a thin facade; implementation ownership lives under `telegram/`.

## Module Ownership

- `telegram/dispatcher.py`: `getUpdates` polling, duplicate-poll guard, update dispatch.
- `telegram/handlers.py`: active command handler implementation.
- `telegram/guards.py`: admin/private/group command authorization and command set constants.
- `telegram/menu.py`: BotFather command menu sync.
- `telegram/messages.py`: user-visible help/status/watchlist/log text builders.
- `telegram/offsets.py`: `telegram_offset.txt` persistence.
- `telegram/api.py`: Telegram HTTP calls.
- `telegram/settings.py`: Telegram token/chat/runtime paths.
- `telegram_commands.py`: compatibility facade imported by `main.py` and legacy tests/tools.

## Compatibility Contract

The active command set is unchanged:

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

Group commands remain disabled. All active commands are admin-private only.

## Runtime Config Writes

Commands that mutate runtime config use `remote_config.update_config(mutator)`.
This preserves runtime config locking for:

- `/scan_now`
- `/scalp_on` and `/scalp_off`
- filter toggles
- `/add_symbol`
- `/remove_symbol`

## Polling And Menu Sync

`ScannerRuntime` remains the owner of one-time command menu sync. Polling does not sync commands.
This prevents normal startup from repeatedly calling BotFather menu updates.

`telegram/dispatcher.py` owns polling and uses `telegram/offsets.py` for persistent update offsets.

## Deferred

- Split handlers by command family if the command set grows.
- Move Telegram polling to a separate process only if a dedicated Telegram service is reintroduced.
- Move hardcoded chat IDs into local config with an explicit compatibility migration.
