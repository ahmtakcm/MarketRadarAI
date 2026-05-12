# MarketRadarAI MarketDataService

`core.market_data_service` is the market-data boundary between resolved exchange symbols and the current MEXC client.

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

## Future Multi-Source Use

Binance, TradingView, or other sources can implement the same service protocol. Symbol interpretation must still remain in `SymbolResolver`, and supported/unsupported routing must still remain in `AssetUniverse`.
