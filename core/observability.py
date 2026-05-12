def safe_symbols(values):
    result = []
    seen = set()
    for value in values or []:
        sym = str(value or "").upper().strip()
        if sym and sym not in seen:
            result.append(sym)
            seen.add(sym)
    return result


def active_modes_text(active_modes):
    return ",".join(active_modes) or "-"


def build_startup_metadata(cfg, active_modes, state_path, runtime_config_path, exchange_name="MEXC"):
    return {
        "exchange": exchange_name,
        "active_modes": active_modes_text(active_modes),
        "watchlist_count": len(safe_symbols(cfg.get("watchlist", {}).get("symbols", []))),
        "state_path": str(state_path),
        "runtime_config_path": str(runtime_config_path),
    }


def format_startup_metadata(metadata):
    return (
        "MarketRadarAI startup | exchange={exchange} | active_modes={active_modes} | "
        "watchlist_count={watchlist_count} | state_path={state_path} | "
        "runtime_config_path={runtime_config_path}"
    ).format(**metadata)


def build_scan_observation(active_modes, symbols):
    return {
        "active_modes": active_modes_text(active_modes),
        "symbol_count": len(safe_symbols(symbols)),
    }


def format_scan_observation(prefix, observation):
    return (
        f"MarketRadarAI scan {prefix} | active_modes={observation['active_modes']} | "
        f"symbol_count={observation['symbol_count']}"
    )
