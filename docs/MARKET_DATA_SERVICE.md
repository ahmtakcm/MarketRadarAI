# MarketRadarAI MarketDataService

`core.market_data_service` is the market-data boundary between resolved exchange symbols and the current MEXC client.
Service, repository, or directory renames do not change the market-data boundary.

## Responsibilities

- Accept already-resolved exchange symbols.
- Delegate candle fetching to `core.exchange_client`.
- Delegate active futures symbol discovery to `core.exchange_client`.
- Provide scanner kline limits.
- Keep MEXC-specific REST details outside scanner orchestration.

## Non-Responsibilities

- No user-input interpretation.
- No alias resolution.
- No substring guessing.
- No symbol normalization.
- No fallback from unsupported symbols.

## Current Flow

User Input -> SymbolResolver -> AssetUniverse -> SymbolCatalog -> MarketDataService -> Scanner -> Telegram Output

`ScannerRuntime` receives the supported symbols from `AssetUniverse` and injects `MarketDataService` into scanner and performance tracking calls.

Telegram watchlist commands use the same symbol resolution path for visibility, but Telegram runtime does not interpret market data. It only reports supported/unsupported results and updates runtime config through locked config helpers.

## Future Multi-Source Use

Binance, TradingView, or other sources can implement the same service protocol. Symbol interpretation must still remain in `SymbolResolver`, and supported/unsupported routing must still remain in `AssetUniverse`.
