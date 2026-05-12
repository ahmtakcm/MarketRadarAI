from __future__ import annotations

from dataclasses import dataclass

from telegram.settings import ADMIN_CHAT_ID, GROUP_CHAT_ID

ADMIN_PRIVATE_COMMANDS = {
    "/help",
    "/health",
    "/status",
    "/scan_now",
    "/restart",
    "/modes",
    "/scalp_on",
    "/scalp_off",
    "/filters",
    "/fake_filter_on",
    "/fake_filter_off",
    "/volume_filter_on",
    "/volume_filter_off",
    "/watchlist",
    "/add_symbol",
    "/remove_symbol",
    "/performance_today",
    "/log",
    "/error_log",
}

# Group commands intentionally disabled for now.
GROUP_SAFE_COMMANDS = set()


@dataclass(frozen=True)
class CommandAccess:
    chat_id: str
    command: str
    is_admin_private: bool
    is_group_chat: bool
    allowed: bool
    known_admin_command: bool


def normalize_command(text: str) -> str:
    text = str(text or "").strip()
    if not text.startswith("/"):
        return ""
    return text.split()[0].lower().split("@", 1)[0]


def check_command_access(message) -> CommandAccess:
    chat_id = str(message.get("chat", {}).get("id", ""))
    command = normalize_command(message.get("text", ""))
    is_admin_private = chat_id == ADMIN_CHAT_ID
    is_group_chat = chat_id == GROUP_CHAT_ID
    known_admin_command = command in ADMIN_PRIVATE_COMMANDS

    if is_admin_private:
        allowed = known_admin_command
    elif is_group_chat:
        allowed = command in GROUP_SAFE_COMMANDS
    else:
        allowed = False

    return CommandAccess(
        chat_id=chat_id,
        command=command,
        is_admin_private=is_admin_private,
        is_group_chat=is_group_chat,
        allowed=allowed,
        known_admin_command=known_admin_command,
    )
