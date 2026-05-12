# MarketRadarAI Symbol Intelligence

MarketRadarAI resolves user-facing symbols before they can reach scanner or market-data calls.

## Pipeline

User Input -> SymbolResolver -> AssetUniverse -> SymbolCatalog -> MarketDataService -> Scanner -> Telegram Output

## Responsibility Boundaries

- `core.symbol_resolver.SymbolResolver` is the only symbol interpretation authority. It normalizes input, checks exact exchange symbols, resolves explicit aliases, and returns `SymbolResolution`.
- `core.asset_universe.resolve_asset_universe` aggregates requested symbols and splits them into supported and unsupported lists by using resolver output.
- `core.symbol_catalog` is read-only enrichment metadata. It must not validate, route, or rewrite symbols.
- `core.market_data_service` is the market-data boundary. It delegates to `core.exchange_client` and should receive already-resolved exchange symbols.
- `core.scanner` should scan only supported symbols provided by `ScannerRuntime`.

## Hard Rules

- No implicit substring guessing.
- No runtime regex patching.
- No monkey patching in production code.
- Unknown symbols remain unsupported and visible.
- Resolver must not call exchange APIs.
- AssetUniverse must not invent aliases outside resolver output.

## Current Gaps

- `MarketDataService` is a thin boundary over `core.exchange_client`; full multi-source routing is still deferred.
- Telegram command runtime is split under `telegram/`; `telegram_commands.py` remains a compatibility facade.
- Runtime config writes still need file locking or compare-and-swap.
