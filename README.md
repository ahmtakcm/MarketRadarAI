# MarketRadarAI

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ahmtakcm/mexc-tarama-bot)

[![RepoWiki](https://repowiki.com/badge.svg)](https://repowiki.com/ahmtakcm/mexc-tarama-bot)

MarketRadarAI is a multi-timeframe market scanning and Telegram signal notification bot.
The current market-data source is MEXC futures. MEXC is a data-source detail, not the product identity.

The repository name can stay `mexc-tarama-bot` for now, but user-facing project identity should refer to MarketRadarAI.

## Current Runtime Contract

- Production runs from `main` only.
- Feature branches are for PR validation and must not be kept running permanently on the server.
- `main.py` owns the scanner loop, scheduling, symbol refresh, signal generation, and state writes.
- `telegram_commands.py` owns the active Telegram command behavior.
- The existing Telegram command set must stay backward compatible.
- Existing config values and scanner flow must not change in hardening-only PRs.

## Configuration And State

- `settings.json`: local machine settings and Telegram credentials. This file is ignored by git.
- `settings.example.json`: safe template for local settings.
- `remote_config.example.json`: safe runtime config template.
- `remote_config.json`: legacy runtime config seed kept for backward compatibility.
- `runtime/remote_config.json`: mutable runtime/user config used by Telegram commands and scanner controls.
- `data/`: runtime state and signal/performance journals.
- `storage/`: runtime locks and cached exchange symbol data.
- `logs/`: runtime logs.

## Asset Universe

MarketRadarAI keeps the requested watchlist separate from the symbols supported by the active data source.
Unsupported entries remain visible in startup logs and Telegram `/watchlist`; they are not silently scanned or dropped.

See `docs/RUNTIME_BEHAVIOR.md`, `docs/ASSET_UNIVERSE.md`, `docs/SIGNAL_LIFECYCLE.md`, `docs/ARCHITECTURE.md`, and `docs/DEPLOYMENT.md` for the current behavior map, persistence inventory, deployment checklist, and deferred hardening work.


