from __future__ import annotations

import os
import sys
import threading

from remote_config import get_active_modes, update_config


def restart_process(delay_seconds=1.5):
    def do_restart():
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Timer(delay_seconds, do_restart).start()


def set_config_value(section: str, key: str, value) -> None:
    def mutate(current):
        current.setdefault(section, {})[key] = value

    update_config(mutate)


def handle_scan_now(reply) -> None:
    set_config_value("runtime", "force_scan_once", True)
    reply("Anlik tarama tetiklendi. Aktif modlar icin mum kapanisi beklenmeden tarama baslatiliyor.")


def handle_restart(reply) -> None:
    reply("Bot process yeniden baslatiliyor...")
    restart_process()


def handle_modes(cfg, reply) -> None:
    active_modes = get_active_modes(cfg)
    reply(
        "MODLAR\n\n"
        f"Scalp: {'ON' if cfg['modes'].get('scalp') else 'OFF'}\n"
        f"Intraday: {'ON' if cfg['modes'].get('intraday') else 'OFF'}\n"
        f"Midterm: {'ON' if cfg['modes'].get('midterm') else 'OFF'}\n\n"
        f"Aktif calisan: {', '.join(active_modes) or 'Yok'}\n"
        "Not: /scan_now aktif modlari anlik tarar."
    )


def handle_scalp_toggle(cmd: str, reply) -> None:
    state = cmd.strip("/").split("_")[1]
    set_config_value("modes", "scalp", state == "on")
    reply(f"Scalp mode {'enabled' if state == 'on' else 'disabled'}.")


def handle_filters(cfg, reply) -> None:
    reply(
        "FILTRELER\n\n"
        f"Fake breakout: {'ON' if cfg['filters'].get('fake_breakout_filter') else 'OFF'}\n"
        f"Volume: {'ON' if cfg['filters'].get('volume_confirmation') else 'OFF'}"
    )


def handle_filter_toggle(cmd: str, reply) -> None:
    if cmd == "/fake_filter_on":
        set_config_value("filters", "fake_breakout_filter", True)
        reply("Fake breakout filtresi acildi.")
        return
    if cmd == "/fake_filter_off":
        set_config_value("filters", "fake_breakout_filter", False)
        reply("Fake breakout filtresi kapatildi.")
        return
    if cmd == "/volume_filter_on":
        set_config_value("filters", "volume_confirmation", True)
        reply("Volume filtresi acildi.")
        return
    if cmd == "/volume_filter_off":
        set_config_value("filters", "volume_confirmation", False)
        reply("Volume filtresi kapatildi.")
