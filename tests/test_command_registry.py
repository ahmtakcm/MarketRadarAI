import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commands.registry import admin_commands, public_commands  # noqa: E402

PRODUCTION_COMMANDS = {
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


def test_passive_registry_matches_current_production_commands():
    assert {cmd.command for cmd in admin_commands()} == PRODUCTION_COMMANDS


def test_group_commands_remain_disabled_in_passive_registry():
    assert public_commands() == []
