from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

COMMANDS_PATH = REPO_ROOT / "BOTFATHER_COMMANDS.txt"
COMMAND_RE = re.compile(r"^[a-z0-9_]{1,32}$")

SCOPES = {
    "default": {"type": "default"},
    "private": {"type": "all_private_chats"},
    "group": {"type": "all_group_chats"},
}


def parse_commands(path: Path):
    commands = []
    seen = set()

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue

        if " - " in raw:
            command, description = raw.split(" - ", 1)
        elif "-" in raw:
            command, description = raw.split("-", 1)
        else:
            continue

        command = command.strip().lstrip("/").lower()
        description = description.strip()[:256]

        if not command or command in seen:
            continue
        if not COMMAND_RE.match(command):
            print(f"SKIP invalid command: {command}")
            continue
        if not description:
            description = command

        commands.append({"command": command, "description": description})
        seen.add(command)

    if not commands:
        raise RuntimeError(f"No commands parsed from {path}")

    if len(commands) > 100:
        raise RuntimeError(f"Telegram supports at most 100 commands, got {len(commands)}")

    return commands


def set_commands(token: str, commands, scope_name: str):
    scope = SCOPES[scope_name]
    response = requests.post(
        f"https://api.telegram.org/bot{token}/setMyCommands",
        json={"commands": commands, "scope": scope},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"setMyCommands failed for {scope_name}: {data}")
    print(f"setMyCommands ok: scope={scope_name} count={len(commands)}")


def main():
    parser = argparse.ArgumentParser(description="Sync BOTFATHER_COMMANDS.txt to Telegram bot command menu.")
    parser.add_argument(
        "--scope",
        choices=["default", "private", "group", "all"],
        default="all",
        help="Command menu scope to update.",
    )
    args = parser.parse_args()

    from config import get_telegram_credentials

    token, _chat_id = get_telegram_credentials()
    if not token:
        raise RuntimeError("Telegram bot token is missing")

    commands = parse_commands(COMMANDS_PATH)
    scope_names = list(SCOPES) if args.scope == "all" else [args.scope]

    for scope_name in scope_names:
        set_commands(token, commands, scope_name)

    print("Telegram command menu sync completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
