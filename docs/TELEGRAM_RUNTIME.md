# MarketRadarAI Telegram Runtime

Telegram runtime behavior remains backward compatible with the previous `telegram_commands.py` surface.
`telegram_commands.py` is now a thin facade; implementation ownership lives under `telegram/`.
Service or repository renames do not change Telegram command names or authorization behavior.

## Module Ownership

- `telegram/dispatcher.py`: `getUpdates` polling, duplicate-poll guard, update dispatch.
- `telegram/handlers.py`: active command routing and guard integration.
- `telegram/command_controls.py`: scan/restart/mode/filter command family.
- `telegram/command_watchlist.py`: watchlist add/remove/display command family.
- `telegram/command_reports.py`: help/status/health/log/report command family.
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

## Environment

- `TELEGRAM_BOT_TOKEN`: Telegram bot token.
- `TELEGRAM_ADMIN_CHAT_ID`: admin private chat override. Default remains the legacy production admin chat.
- `TELEGRAM_GROUP_CHAT_ID`: group chat override. Group commands remain disabled unless explicitly changed in code.
- `TELEGRAM_ALLOWED_CHAT_ID`: legacy single-chat compatibility fallback.

## Polling And Menu Sync

`ScannerRuntime` remains the owner of one-time command menu sync. Polling does not sync commands.
This prevents normal startup from repeatedly calling BotFather menu updates.

`telegram/dispatcher.py` owns polling and uses `telegram/offsets.py` for persistent update offsets.

## Deferred

- Move Telegram polling to a separate process only if a dedicated Telegram service is reintroduced.
- Move Telegram chat IDs fully into local config if env-based overrides are not enough.
