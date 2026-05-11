from __future__ import annotations

from commands.registry import COMMANDS

COMMAND_MAP = {
    cmd.command: cmd
    for cmd in COMMANDS
}


def normalize_command(text: str) -> str:
    cmd = text.strip().split()[0]

    if "@" in cmd:
        cmd = cmd.split("@")[0]

    return cmd.lower()


def resolve_command(text: str):
    cmd = normalize_command(text)
    return COMMAND_MAP.get(cmd)
