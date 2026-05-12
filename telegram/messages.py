from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from core.asset_universe import (
    AssetResolution,
    build_watchlist_text,
    normalize_asset_symbols,
    resolve_asset_universe,
)
from core.market_data_service import get_valid_futures_symbols
from health_monitor import START_TIME, build_health_text, format_duration
from remote_config import get_active_modes, get_config_path, load_config
from signal_journal import build_performance_today_text
from telegram.settings import BASE_DIR


def _resolve_watchlist(symbols) -> AssetResolution | None:
    try:
        valid_symbols = get_valid_futures_symbols()
    except Exception:
        logging.exception("Watchlist symbol resolution failed")
        return None
    return resolve_asset_universe(symbols, valid_symbols)


def _runtime_config_short_path() -> str:
    path = get_config_path()
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def build_status():
    cfg = load_config()
    active_modes = get_active_modes(cfg)
    watchlist_symbols = normalize_asset_symbols(cfg.get("watchlist", {}).get("symbols", []))
    resolution = _resolve_watchlist(watchlist_symbols) if watchlist_symbols else None

    scalp = bool(cfg["modes"].get("scalp"))
    intraday = bool(cfg["modes"].get("intraday"))
    midterm = bool(cfg["modes"].get("midterm"))

    if (not scalp) and intraday and midterm:
        mode_note = "Normal duzen: Intraday + Midterm aktif. Scalp manuel kapali."
    elif scalp and intraday and midterm:
        mode_note = "Scalp dahil 3 mod aktif."
    else:
        mode_note = "Acik modlara gore calisiyor."

    if resolution:
        universe_text = (
            f"Watchlist: {resolution.requested_count} kayit | "
            f"supported {resolution.supported_count} | unsupported {resolution.unsupported_count}"
        )
    elif watchlist_symbols:
        universe_text = f"Watchlist: {len(watchlist_symbols)} kayit | supported/unsupported dogrulanamadi"
    else:
        universe_text = "Watchlist: 0 kayit | tarama yapilmaz"

    health_text = (
        f"Uptime: {format_duration(time.time() - START_TIME)} | "
        f"PID: {os.getpid()} | config: {_runtime_config_short_path()}"
    )

    return (
        "MarketRadarAI STATUS\n"
        "====================\n\n"
        "SAGLIK\n"
        f"{health_text}\n\n"
        "MODLAR\n"
        f"Scalp: {'ON' if scalp else 'OFF'}\n"
        f"Intraday: {'ON' if intraday else 'OFF'}\n"
        f"Midterm: {'ON' if midterm else 'OFF'}\n"
        f"Aktif calisan: {', '.join(active_modes) or 'Yok'}\n"
        f"Not: {mode_note}\n\n"
        "ASSET UNIVERSE\n"
        f"{universe_text}\n\n"
        "FILTRELER\n"
        f"Fake breakout: {'ON' if cfg['filters'].get('fake_breakout_filter') else 'OFF'}\n"
        f"Volume: {'ON' if cfg['filters'].get('volume_confirmation') else 'OFF'}\n"
        f"Cooldown: {cfg['limits'].get('cooldown_minutes')} dk"
    )


def read_tail(path: Path, lines=40) -> str:
    if not path.exists():
        return "Dosya bulunamadi."
    data = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(data[-lines:])[-3500:]


def help_text():
    return (
        "MarketRadarAI HELP\n"
        "==================\n\n"
        "Durum ve loglar\n"
        "/help - Bu yardim menusu\n"
        "/status - Bot, mod, watchlist ve runtime ozeti\n"
        "/health - Sistem sagligi\n"
        "/log - Son loglar\n"
        "/error_log - Hata loglari\n\n"
        "Tarama\n"
        "/scan_now - Aktif modlari hemen tara\n\n"
        "Bot kontrol\n"
        "/restart - Bot process yeniden baslat\n\n"
        "Modlar\n"
        "/modes - Aktif modlari goster\n"
        "/scalp_on - Scalp modunu ac\n"
        "/scalp_off - Scalp modunu kapat\n\n"
        "Filtreler\n"
        "/filters - Filtre durumunu goster\n"
        "/fake_filter_on - Fake breakout filtresini ac\n"
        "/fake_filter_off - Fake breakout filtresini kapat\n"
        "/volume_filter_on - Volume filtresini ac\n"
        "/volume_filter_off - Volume filtresini kapat\n\n"
        "Watchlist\n"
        "/watchlist - Desteklenen/desteklenmeyen sembolleri goster\n"
        "/add_symbol BTCUSDT - Sembol ekle\n"
        "/remove_symbol BTCUSDT - Sembol cikar\n\n"
        "Rapor\n"
        "/performance_today - Gunluk sinyal raporu\n\n"
        "Not: Tum komutlar admin private chat icindir; grup komutlari kapali."
    )


def watchlist_text(cfg):
    symbols = cfg.get("watchlist", {}).get("symbols", [])
    if not symbols:
        return (
            "MarketRadarAI WATCHLIST\n\n"
            "Liste bos. Bot tarama yapmaz.\n\n"
            "Sembol eklemek icin: /add_symbol BTCUSDT"
        )

    resolution = _resolve_watchlist(symbols)
    if resolution is None:
        return (
            "MarketRadarAI WATCHLIST\n\n"
            f"Toplam: {len(symbols)}\n"
            f"Kayitli semboller: {', '.join(symbols)}\n\n"
            "Desteklenen/desteklenmeyen ayrimi su an dogrulanamadi.\n"
            "Hata: borsa sembol listesi alinamadi"
        )

    return build_watchlist_text(resolution)


def log_text() -> str:
    return "SON LOG\n\n" + read_tail(BASE_DIR / "logs" / "app.log", 25)


def error_log_text() -> str:
    raw = read_tail(BASE_DIR / "logs" / "app.log", 250)
    lines = raw.splitlines()
    important = [line for line in lines if any(marker in line for marker in ["ERROR", "Traceback", "Exception"])]

    if important:
        return "HATA LOG\n\n" + "\n".join(important[-30:])
    return "Son loglarda kritik hata yok."


__all__ = [
    "build_health_text",
    "build_performance_today_text",
    "build_status",
    "error_log_text",
    "help_text",
    "log_text",
    "watchlist_text",
]
