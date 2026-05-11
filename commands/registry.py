from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandDefinition:
    command: str
    description: str
    admin_only: bool = False
    group_safe: bool = False


COMMANDS = [
    CommandDefinition(
        command="/help",
        description="Komut listesi",
    ),
    CommandDefinition(
        command="/health",
        description="Sistem sagligi",
    ),
    CommandDefinition(
        command="/status",
        description="Bot durumu",
    ),
    CommandDefinition(
        command="/scan_now",
        description="Anlik tarama",
        admin_only=True,
    ),
    CommandDefinition(
        command="/restart",
        description="Bot process restart",
        admin_only=True,
    ),
    CommandDefinition(
        command="/modes",
        description="Mod durumu",
    ),
    CommandDefinition(
        command="/scalp_on",
        description="Scalp ac",
        admin_only=True,
    ),
    CommandDefinition(
        command="/scalp_off",
        description="Scalp kapat",
        admin_only=True,
    ),
    CommandDefinition(
        command="/filters",
        description="Filtre durumu",
    ),
    CommandDefinition(
        command="/fake_filter_on",
        description="Fake filtre ac",
        admin_only=True,
    ),
    CommandDefinition(
        command="/fake_filter_off",
        description="Fake filtre kapat",
        admin_only=True,
    ),
    CommandDefinition(
        command="/volume_filter_on",
        description="Volume filtre ac",
        admin_only=True,
    ),
    CommandDefinition(
        command="/volume_filter_off",
        description="Volume filtre kapat",
        admin_only=True,
    ),
    CommandDefinition(
        command="/watchlist",
        description="Izleme listesi",
    ),
    CommandDefinition(
        command="/add_symbol",
        description="Sembol ekle",
        admin_only=True,
    ),
    CommandDefinition(
        command="/remove_symbol",
        description="Sembol cikar",
        admin_only=True,
    ),
    CommandDefinition(
        command="/performance_today",
        description="Gunluk performans",
    ),
    CommandDefinition(
        command="/log",
        description="Son loglar",
    ),
    CommandDefinition(
        command="/error_log",
        description="Hata loglari",
        admin_only=True,
    ),
]


def public_commands():
    return [x for x in COMMANDS if x.group_safe]


def admin_commands():
    return COMMANDS
