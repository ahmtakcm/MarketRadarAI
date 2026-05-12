# MarketRadarAI Asset Universe

MarketRadarAI separates the user watchlist from the symbols that a specific market-data source can scan.

## Current Source

- Active source: MEXC futures.
- Current supported asset class: crypto futures symbols available from MEXC.
- Repo and service names may still contain `mexc-tarama-bot` for backward compatibility.

## Resolution Flow

1. Runtime config stores the requested watchlist in `runtime/remote_config.json`.
2. `core.asset_universe.resolve_asset_universe` normalizes and de-duplicates requested symbols.
3. The resolver compares requested symbols with the active exchange symbol universe.
4. Supported symbols are passed to scanner orchestration.
5. Unsupported symbols stay visible in logs and Telegram `/watchlist`; they are not silently discarded.

## Production Example

If the watchlist has nine symbols and MEXC currently supports only `BTCUSDT` and `ETHUSDT`, the scan universe is:

- Supported: `BTCUSDT`, `ETHUSDT`
- Unsupported for current source: `AAPLUSDT`, `TSLAUSDT`, `AMZNUSDT`, `METAUSDT`, `MSFTUSDT`, `XAUUSDT`, `XAGUSDT`

This is not a scanner failure. It means the current data source is crypto-only for this bot contract.

## Migration Direction

Future multi-source support should add real source adapters before enabling non-crypto symbols. Until then, equities and commodities remain unsupported watchlist entries for the MEXC source.
