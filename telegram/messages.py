from __future__ import annotations

import logging
from pathlib import Path

from core.asset_universe import build_watchlist_text, resolve_asset_universe
from core.market_data_service import get_valid_futures_symbols
from health_monitor import build_health_text
from remote_config import get_active_modes, load_config
from signal_journal import build_performance_today_text
from telegram.settings import BASE_DIR


def build_status():
    cfg = load_config()
    active_modes = get_active_modes(cfg)

    scalp = bool(cfg["modes"].get("scalp"))
    intraday = bool(cfg["modes"].get("intraday"))
    midterm = bool(cfg["modes"].get("midterm"))

    if (not scalp) and intraday and midterm:
        mode_note = "Normal duzen: Intraday + Midterm aktif. Scalp manuel kapali."
    elif scalp and intraday and midterm:
        mode_note = "Scalp dahil 3 mod aktif."
    else:
        mode_note = "Acik modlara gore calisiyor."

    return (
        "BOT DURUMU\n\n"
        "Ping: pong\n\n"
        "MODLAR\n"
        f"Scalp: {'ON' if scalp else 'OFF'}\n"
        f"Intraday: {'ON' if intraday else 'OFF'}\n"
        f"Midterm: {'ON' if midterm else 'OFF'}\n"
        f"Aktif calisan: {', '.join(active_modes) or 'Yok'}\n"
        f"Not: {mode_note}\n\n"
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
        "MarketRadarAI KOMUTLARI\n"
        "=======================\n\n"
        "[1] DURUM\n"
        "/status      Bot durumu + ping\n"
        "/health      Sistem sagligi\n"
        "/log         Son loglar\n"
        "/error_log   Hata loglari\n\n"
        "[2] TARAMA\n"
        "/scan_now    Aktif modlari mum kapanisi beklemeden tara\n\n"
        "[3] BOT\n"
        "/restart     Bot process yeniden baslat\n\n"
        "[4] MODLAR\n"
        "/modes       Aktif modlari goster\n"
        "/scalp_on    Scalp modunu ac\n"
        "/scalp_off   Scalp modunu kapat\n\n"
        "[5] FILTRELER\n"
        "/filters             Filtre durumunu goster\n"
        "/fake_filter_on      Fake breakout filtresini ac\n"
        "/fake_filter_off     Fake breakout filtresini kapat\n"
        "/volume_filter_on    Volume filtresini ac\n"
        "/volume_filter_off   Volume filtresini kapat\n\n"
        "[6] WATCHLIST\n"
        "/watchlist              Izleme listesini goster\n"
        "/add_symbol BTCUSDT     Sembol ekle\n"
        "/remove_symbol BTCUSDT  Sembol cikar\n\n"
        "[7] RAPOR\n"
        "/performance_today   Gunluk sinyal raporu\n\n"
        "Not: Grup komutlari kapali. Tum komutlar admin private chat icindir."
    )


def watchlist_text(cfg):
    symbols = cfg.get("watchlist", {}).get("symbols", [])
    if not symbols:
        return (
            "MarketRadarAI WATCHLIST\n\n"
            "Liste bos. Bot tarama yapmaz.\n\n"
            "Sembol eklemek icin: /add_symbol BTCUSDT"
        )

    try:
        valid_symbols = get_valid_futures_symbols()
    except Exception as e:
        logging.exception("Watchlist symbol resolution failed")
        return (
            "MarketRadarAI WATCHLIST\n\n"
            f"Toplam: {len(symbols)}\n"
            f"Kayitli semboller: {', '.join(symbols)}\n\n"
            "Desteklenen/desteklenmeyen ayrimi su an dogrulanamadi.\n"
            f"Hata: {str(e)[:120]}"
        )

    return build_watchlist_text(resolve_asset_universe(symbols, valid_symbols))


def log_text() -> str:
    return "ğŸ“œ SON LOG\n\n" + read_tail(BASE_DIR / "logs" / "app.log", 25)


def error_log_text() -> str:
    raw = read_tail(BASE_DIR / "logs" / "app.log", 250)
    lines = raw.splitlines()
    important = [line for line in lines if any(marker in line for marker in ["ERROR", "Traceback", "Exception"])]

    if important:
        return "ğŸš¨ HATA LOG\n\n" + "\n".join(important[-30:])
    return "âœ… Son loglarda kritik hata yok."


__all__ = [
    "build_health_text",
    "build_performance_today_text",
    "build_status",
    "error_log_text",
    "help_text",
    "log_text",
    "watchlist_text",
]
