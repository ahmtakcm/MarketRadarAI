# MarketRadarAI Symbol Intelligence

MarketRadarAI resolves user-facing symbols before they can reach scanner or market-data calls.

## Pipeline

User Input -> SymbolResolver -> AssetUniverse -> SymbolCatalog -> MarketDataService -> Scanner -> Telegram Output

## Responsibility Boundaries

- `core.symbol_resolver.SymbolResolver` is the only symbol interpretation authority. It normalizes input, checks exact exchange symbols, resolves explicit aliases, and returns `SymbolResolution`.
- `core.asset_universe.resolve_asset_universe` aggregates requested symbols and splits them into supported and unsupported lists by using resolver output.
- `core.symbol_catalog` is read-only enrichment metadata. It must not validate, route, or rewrite symbols.
- `core.exchange_client` is the current MEXC market-data boundary. It should receive already-resolved exchange symbols.
- `core.scanner` should scan only supported symbols provided by `ScannerRuntime`.

## Hard Rules

- No implicit substring guessing.
- No runtime regex patching.
- No monkey patching in production code.
- Unknown symbols remain unsupported and visible.
- Resolver must not call exchange APIs.
- AssetUniverse must not invent aliases outside resolver output.

## Current Gaps

- `MarketDataService` is not yet a separate adapter class; `core.exchange_client` is the current implementation boundary.
- `telegram_commands.py` still contains active dispatcher logic in one file.
- Runtime config writes still need file locking or compare-and-swap.
