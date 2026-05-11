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
        group_safe=True,
    ),
    CommandDefinition(
        command="/status",
        description="Bot durumu",
        group_safe=True,
    ),
    CommandDefinition(
        command="/scan_now",
        description="Anlık tarama çalıştır",
        admin_only=True,
    ),
    CommandDefinition(
        command="/start",
        description="Botu aktif et",
        admin_only=True,
    ),
    CommandDefinition(
        command="/stop",
        description="Botu durdur",
        admin_only=True,
    ),
]


def public_commands():
    return [x for x in COMMANDS if x.group_safe]


def admin_commands():
    return COMMANDS
