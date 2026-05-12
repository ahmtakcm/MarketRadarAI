from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

SUPPORTED_ASSET_CLASS = "crypto"
UNSUPPORTED_ASSET_CLASS = "unsupported"


@dataclass(frozen=True)
class AssetResolution:
    requested: list[str]
    supported: list[str]
    unsupported: list[str]
    exchange: str = "MEXC"
    supported_asset_class: str = SUPPORTED_ASSET_CLASS

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
    supported = [symbol for symbol in requested if symbol in exchange_set]
    unsupported = [symbol for symbol in requested if symbol not in exchange_set]
    return AssetResolution(
        requested=requested,
        supported=supported,
        unsupported=unsupported,
        exchange=exchange,
    )


def format_asset_resolution_log(resolution: AssetResolution) -> str:
    return (
        f"MarketRadarAI asset universe | exchange={resolution.exchange} | "
        f"requested={resolution.requested_count} | supported={resolution.supported_count} | "
        f"unsupported={resolution.unsupported_count}"
    )


def build_watchlist_text(resolution: AssetResolution) -> str:
    lines = [
        "MarketRadarAI WATCHLIST",
        "",
        f"Veri kaynagi: {resolution.exchange}",
        f"Toplam: {resolution.requested_count}",
        f"Desteklenen: {resolution.supported_count}",
        f"Desteklenmeyen: {resolution.unsupported_count}",
        "",
    ]

    if resolution.supported:
        lines.extend(
            [
                "Taranacak semboller:",
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

    if resolution.unsupported:
        lines.extend(
            [
                "Desteklenmeyen semboller:",
                ", ".join(resolution.unsupported),
                "",
                f"Not: {resolution.exchange} futures veri kaynagi yalnizca desteklenen crypto sembollerini tarar.",
            ]
        )
    else:
        lines.append("Not: Tum watchlist sembolleri mevcut veri kaynaginda destekleniyor.")

    return "\n".join(lines).strip()
