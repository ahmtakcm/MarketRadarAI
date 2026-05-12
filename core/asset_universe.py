from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from core.symbol_resolver import SymbolResolver

SUPPORTED_ASSET_CLASS = "crypto"
UNSUPPORTED_ASSET_CLASS = "unsupported"


@dataclass(frozen=True)
class AssetResolution:
    requested: list[str]
    supported: list[str]
    unsupported: list[str]
    exchange: str = "MEXC"
    supported_asset_class: str = SUPPORTED_ASSET_CLASS
    resolved_aliases: dict[str, str] = field(default_factory=dict)
    resolution_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def requested_count(self) -> int:
        return len(self.requested)

    @property
    def supported_count(self) -> int:
        return len(self.supported)

    @property
    def unsupported_count(self) -> int:
        return len(self.unsupported)


def normalize_asset_symbol(value: object) -> str:
    return str(value or "").upper().strip()


def normalize_asset_symbols(values: Iterable[object] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        symbol = normalize_asset_symbol(value)
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return result


def resolve_asset_universe(
    requested_symbols: Iterable[object] | None,
    exchange_symbols: Iterable[object] | None,
    exchange: str = "MEXC",
) -> AssetResolution:
    requested = normalize_asset_symbols(requested_symbols)
    exchange_set = set(normalize_asset_symbols(exchange_symbols))
    resolver = SymbolResolver()

    supported: list[str] = []
    unsupported: list[str] = []
    resolved_aliases: dict[str, str] = {}
    resolution_reasons: dict[str, int] = {}
    seen_supported: set[str] = set()

    for symbol in requested:
        resolution = resolver.resolve(symbol, exchange_set)
        resolution_reasons[resolution.reason] = resolution_reasons.get(resolution.reason, 0) + 1
        if resolution.supported and resolution.resolved:
            if resolution.resolved not in seen_supported:
                supported.append(resolution.resolved)
                seen_supported.add(resolution.resolved)
            if resolution.reason == "alias":
                resolved_aliases[symbol] = resolution.resolved
        else:
            unsupported.append(symbol)

    return AssetResolution(
        requested=requested,
        supported=supported,
        unsupported=unsupported,
        exchange=exchange,
        resolved_aliases=resolved_aliases,
        resolution_reasons=resolution_reasons,
    )


def format_asset_resolution_log(resolution: AssetResolution) -> str:
    return (
        f"MarketRadarAI asset universe | exchange={resolution.exchange} | "
        f"requested={resolution.requested_count} | supported={resolution.supported_count} | "
        f"unsupported={resolution.unsupported_count} | "
        f"resolution_reasons={_format_resolution_reasons(resolution.resolution_reasons)}"
    )



def _format_resolution_reasons(reasons: dict[str, int]) -> str:
    ordered_keys = ["exact", "alias", "unsupported", "empty", "alias_target_missing"]
    return ",".join(
        f"{key}:{reasons[key]}"
        for key in ordered_keys
        if reasons.get(key)
    )

def build_watchlist_text(resolution: AssetResolution) -> str:
    lines = [
        "MarketRadarAI WATCHLIST",
        "",
        (
            f"Summary: {resolution.exchange} | requested {resolution.requested_count} | "
            f"supported {resolution.supported_count} | unsupported {resolution.unsupported_count}"
        ),
        "",
    ]

    if resolution.supported:
        lines.extend(
            [
                "Supported scan symbols:",
                ", ".join(resolution.supported),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Taranacak sembol yok.",
                "",
            ]
        )

    if resolution.resolved_aliases:
        lines.append("Resolved aliases:")
        lines.extend(
            f"{requested} -> {resolved}"
            for requested, resolved in resolution.resolved_aliases.items()
        )
        lines.append("")

    if resolution.unsupported:
        lines.extend(
            [
                "Unsupported symbols:",
                ", ".join(resolution.unsupported),
                "",
                f"Not: {resolution.exchange} futures veri kaynagi yalnizca desteklenen crypto sembollerini tarar.",
            ]
        )
    else:
        lines.append("Not: Tum watchlist sembolleri destekleniyor.")

    return "\n".join(lines).strip()
