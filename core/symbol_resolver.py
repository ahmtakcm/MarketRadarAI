from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

DEFAULT_SYMBOL_ALIASES: dict[str, str | dict[str, object]] = {
    "GOLD(XAUT)USDT": "XAUTUSDT",
    "GOLDUSDT": "XAUTUSDT",
    "XAUUSDT": "XAUTUSDT",
    "SILVER(XAG)USDT": "SILVERUSDT",
    "XAGUSDT": "SILVERUSDT",
    "COPPER(XCU)USDT": "COPPERUSDT",
    "XCUUSDT": "COPPERUSDT",
    "GAS(NG)USDT": {
        "preferred": "GASUSDT",
        "alternatives": ["NGASUSDT"],
        "status": "review",
    },
    "NGUSDT": {
        "preferred": "GASUSDT",
        "alternatives": ["NGASUSDT"],
        "status": "review",
    },
    "OIL(WTI)USDT": "USOILUSDT",
    "WTIUSDT": "USOILUSDT",
    "OIL(BRENT)USDT": "UKOILUSDT",
    "BRENTUSDT": "UKOILUSDT",
    "SP500USDT": "SPX500USDT",
    "QQQUSDT": "QQQSTOCKUSDT",
    "TSLA": "TESLAUSDT",
    "TSLAUSDT": "TESLAUSDT",
    "NVDA": "NVIDIAUSDT",
    "NVDAUSDT": "NVIDIAUSDT",
    "HK50": "HK50USDT",
}


@dataclass(frozen=True)
class SymbolResolution:
    requested: str
    resolved: str | None
    supported: bool
    reason: str
    alternatives: list[str] = field(default_factory=list)


def normalize_symbol(value: object) -> str:
    return str(value or "").upper().strip()


class SymbolResolver:
    def __init__(self, aliases: Mapping[str, str | Mapping[str, object]] | None = None) -> None:
        self.aliases = {
            normalize_symbol(key): value
            for key, value in (aliases or DEFAULT_SYMBOL_ALIASES).items()
        }

    def resolve(self, value: object, valid_symbols: set[str]) -> SymbolResolution:
        requested = normalize_symbol(value)
        normalized_valid_symbols = {normalize_symbol(symbol) for symbol in valid_symbols}

        if not requested:
            return SymbolResolution(
                requested=requested,
                resolved=None,
                supported=False,
                reason="empty",
            )

        if requested in normalized_valid_symbols:
            return SymbolResolution(
                requested=requested,
                resolved=requested,
                supported=True,
                reason="exact",
            )

        alias_entry = self.aliases.get(requested)
        if alias_entry is None:
            return SymbolResolution(
                requested=requested,
                resolved=None,
                supported=False,
                reason="unsupported",
            )

        preferred, alternatives = self._parse_alias_entry(alias_entry)
        if preferred in normalized_valid_symbols:
            return SymbolResolution(
                requested=requested,
                resolved=preferred,
                supported=True,
                reason="alias",
                alternatives=[
                    symbol for symbol in alternatives if symbol in normalized_valid_symbols
                ],
            )

        return SymbolResolution(
            requested=requested,
            resolved=None,
            supported=False,
            reason="alias_target_missing",
            alternatives=[
                symbol for symbol in alternatives if symbol in normalized_valid_symbols
            ],
        )

    @staticmethod
    def _parse_alias_entry(alias_entry: str | Mapping[str, object]) -> tuple[str, list[str]]:
        if isinstance(alias_entry, str):
            return normalize_symbol(alias_entry), []

        preferred = normalize_symbol(alias_entry.get("preferred"))
        raw_alternatives = alias_entry.get("alternatives", [])
        alternatives = [
            normalize_symbol(symbol)
            for symbol in raw_alternatives
            if normalize_symbol(symbol)
        ]
        return preferred, alternatives


