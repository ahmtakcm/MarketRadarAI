import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def check_candle_shape(candles):
    required = {"open_time", "close_time", "time", "open", "high", "low", "close", "volume"}
    if not candles:
        return False, "no candles returned"

    missing = required.difference(candles[-1])
    if missing:
        return False, "missing candle keys: " + ", ".join(sorted(missing))

    return True, "ok"


def main():
    parser = argparse.ArgumentParser(description="Run a small MEXC bot smoke check.")
    parser.add_argument("--live", action="store_true", help="Call MEXC endpoints for BTCUSDT validation.")
    args = parser.parse_args()

    from core.symbol_runtime import configured_scan_symbols
    from telegram_commands import telegram_polling_enabled

    symbols, source = configured_scan_symbols()
    print(f"symbols={','.join(symbols)} source={source}")
    print(f"telegram_polling_enabled={telegram_polling_enabled()}")

    if args.live:
        from core.exchange_client import fetch_klines, validate_futures_symbol

        ok, reason = validate_futures_symbol("BTCUSDT")
        print(f"validate_BTCUSDT={ok} reason={reason}")
        if not ok:
            return 1

        candles = fetch_klines("BTCUSDT", "15m", 30)
        ok, reason = check_candle_shape(candles)
        print(f"candle_shape={ok} reason={reason}")
        if not ok:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
