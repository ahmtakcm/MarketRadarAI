from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

from config import REQUESTED_SYMBOLS
from core.asset_universe import (
    format_asset_resolution_log,
    normalize_asset_symbols,
    resolve_asset_universe,
)
from core.exchange_client import fetch_klines, get_kline_limit
from core.observability import build_scan_observation, format_scan_observation
from core.performance_tracker import finalize_pending_signals
from core.scanner import build_signal_message, get_active_symbols, get_daily_commentaries
from core.scheduler import next_sleep_seconds
from core.state_store import load_state, save_state
from remote_config import get_active_modes, load_config, save_config
from signal_journal import append_signal_message, set_last_signal

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BASE_DIR / "storage"
SYMBOL_CACHE_PATH = STORAGE_DIR / "last_active_symbols.json"

STARTUP_SYMBOL_ATTEMPTS = 3
STARTUP_SYMBOL_RETRY_SECONDS = 10
SYMBOL_REFRESH_SECONDS = 300
DEGRADED_REMINDER_SECONDS = 1800

SendTelegram = Callable[[str], None]
PollTelegramCommands = Callable[[SendTelegram], None]
SendLifecycle = Callable[[str, dict[str, object] | None], None]


def _now_text() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def bot_allowed_to_scan() -> bool:
    return True


def is_quiet_mode() -> bool:
    return False


class ScannerRuntime:
    def __init__(
        self,
        send_telegram: SendTelegram,
        poll_telegram_commands: PollTelegramCommands,
        send_lifecycle: SendLifecycle | None = None,
    ) -> None:
        self.send_telegram = send_telegram
        self.poll_telegram_commands = poll_telegram_commands
        self.send_lifecycle = send_lifecycle or (lambda _title, _fields=None: None)
        self._telegram_command_thread_started = False

    def _safe_symbols(self, values) -> list[str]:
        return normalize_asset_symbols(values)

    def _save_symbol_cache(self, symbols, source="live") -> None:
        try:
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "saved_at": _now_text(),
                "source": source,
                "symbols": self._safe_symbols(symbols),
            }
            tmp = SYMBOL_CACHE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, SYMBOL_CACHE_PATH)
        except Exception as e:
            logging.warning("Sembol cache yazılamadı: %s", e)

    def _load_symbol_cache(self):
        try:
            if not SYMBOL_CACHE_PATH.exists():
                return [], None
            data = json.loads(SYMBOL_CACHE_PATH.read_text(encoding="utf-8-sig"))
            symbols = self._safe_symbols(data.get("symbols", []))
            saved_at = data.get("saved_at")
            return symbols, saved_at
        except Exception as e:
            logging.warning("Sembol cache okunamadı: %s", e)
            return [], None

    def _default_fallback_symbols(self) -> list[str]:
        return self._safe_symbols(REQUESTED_SYMBOLS)

    def _fetch_live_symbols_once(self) -> list[str]:
        symbols = self._safe_symbols(get_active_symbols())
        if not symbols:
            raise RuntimeError("Aktif sembol listesi boş geldi")
        return symbols

    def load_symbols_resilient(self):
        last_error = None

        for attempt in range(1, STARTUP_SYMBOL_ATTEMPTS + 1):
            try:
                symbols = self._fetch_live_symbols_once()
                self._save_symbol_cache(symbols, source="live")
                logging.info("Aktif semboller alındı: %s adet", len(symbols))
                self.send_lifecycle(
                    "✅ Bot çalışıyor",
                    {
                        "Tarama durumu": "Başladı",
                        "Geçerli borsa sembol sayısı": len(symbols),
                    },
                )
                return symbols, False, time.time()
            except Exception as e:
                last_error = e
                logging.exception(
                    "Aktif semboller alınamadı, startup denemesi %s/%s: %s",
                    attempt,
                    STARTUP_SYMBOL_ATTEMPTS,
                    e,
                )
                if attempt < STARTUP_SYMBOL_ATTEMPTS:
                    time.sleep(STARTUP_SYMBOL_RETRY_SECONDS)

        cached_symbols, cached_at = self._load_symbol_cache()
        if cached_symbols:
            fallback = cached_symbols
            source = f"cache ({cached_at or 'tarih yok'})"
        else:
            fallback = self._default_fallback_symbols()
            source = "default settings.json symbols"

        if not fallback:
            fallback = ["BTCUSDT", "ETHUSDT", "XAUUSDT", "XAGUSDT"]
            source = "hardcoded emergency fallback"

        logging.warning(
            "Aktif sembol listesi alınamadı; fallback sembollerle devam ediliyor | kaynak=%s | sembol=%s | hata=%s",
            source,
            ", ".join(fallback),
            last_error,
        )
        self.send_lifecycle(
            "⚠️ Bot başladı ama borsa sembol listesi alınamadı",
            {
                "Durum": "Fallback sembollerle tarama sürecek",
                "Kaynak": source,
                "Sembol sayısı": len(fallback),
                "Son hata": str(last_error)[:220],
            },
        )
        return fallback, True, time.time()

    def maybe_refresh_symbols(self, current_symbols, degraded, last_refresh, last_degraded_notice):
        now = time.time()
        if now - last_refresh < SYMBOL_REFRESH_SECONDS:
            return current_symbols, degraded, last_refresh, last_degraded_notice

        try:
            symbols = self._fetch_live_symbols_once()
            self._save_symbol_cache(symbols, source="live")
            logging.info("Aktif sembol listesi yenilendi: %s adet", len(symbols))
            if degraded:
                self.send_lifecycle(
                    "✅ Borsa sembol listesi tekrar alındı",
                    {
                        "Durum": "Normal tarama moduna dönüldü",
                        "Sembol sayısı": len(symbols),
                        "Kaynak": "live",
                    },
                )
            return symbols, False, now, 0

        except Exception as e:
            logging.exception("Aktif sembol listesi yenilenemedi; mevcut/fallback listeyle devam: %s", e)
            if not degraded:
                self.send_lifecycle(
                    "⚠️ Borsa sembol listesi yenilenemedi",
                    {
                        "Durum": "Son bilinen sembol listesiyle tarama sürecek",
                        "Sembol sayısı": len(current_symbols),
                        "Son hata": str(e)[:220],
                    },
                )
                last_degraded_notice = now
            elif now - last_degraded_notice >= DEGRADED_REMINDER_SECONDS:
                self.send_lifecycle(
                    "⚠️ Borsa sembol listesi hâlâ alınamıyor",
                    {
                        "Durum": "Fallback/son bilinen listeyle tarama sürüyor",
                        "Sembol sayısı": len(current_symbols),
                        "Son hata": str(e)[:220],
                    },
                )
                last_degraded_notice = now
            return current_symbols, True, now, last_degraded_notice

    def consume_force_scan_request(self) -> bool:
        try:
            cfg = load_config()
            runtime = cfg.setdefault("runtime", {})
            if runtime.get("force_scan_once"):
                runtime["force_scan_once"] = False
                save_config(cfg)
                watchlist_count = len(self._safe_symbols(cfg.get("watchlist", {}).get("symbols", [])))
                logging.info(
                    "Telegram /scan_now force_scan_once consumed | active_modes=%s | watchlist_count=%s",
                    ",".join(get_active_modes(cfg)) or "-",
                    watchlist_count,
                )
                logging.info("Telegram /scan_now isteği alındı; tarama hemen çalıştırılacak")
                return True
        except Exception as e:
            logging.exception("force_scan_once kontrol hatası: %s", e)
        return False

    def apply_watchlist_filter(self, discovered_symbols) -> list[str]:
        cfg = load_config()
        wanted = self._safe_symbols(cfg.get("watchlist", {}).get("symbols", []))

        if not wanted:
            logging.warning("Watchlist boş; tarama yapılmayacak.")
            return []

        resolution = resolve_asset_universe(wanted, discovered_symbols)
        logging.info(format_asset_resolution_log(resolution))

        if resolution.unsupported:
            logging.warning(
                "Watchlist icinde veri kaynaginda desteklenmeyen semboller var: %s",
                ", ".join(resolution.unsupported),
            )

        return resolution.supported

    def sleep_with_command_polling(self, seconds) -> None:
        end_time = time.time() + max(1, int(seconds))

        while time.time() < end_time:
            try:
                self.poll_telegram_commands(self.send_telegram)
                cfg = load_config()
                if cfg.get("runtime", {}).get("force_scan_once"):
                    logging.info("/scan_now bayrağı görüldü; uyku erken kesiliyor")
                    return
            except Exception as e:
                logging.exception("Uyku sırasında Telegram komut okuma hatası: %s", e)

            time.sleep(1)

    def _telegram_command_thread_loop(self) -> None:
        logging.info("Telegram komut thread'i başladı")
        while True:
            try:
                self.poll_telegram_commands(self.send_telegram)
            except Exception as e:
                logging.exception("Telegram komut thread hatası: %s", e)
            time.sleep(1.5)

    def start_telegram_command_thread(self) -> None:
        if self._telegram_command_thread_started:
            return
        thread = threading.Thread(
            target=self._telegram_command_thread_loop,
            name="telegram-command-poller",
            daemon=True,
        )
        thread.start()
        self._telegram_command_thread_started = True

    def run_scan_cycle(self, state, symbols) -> None:
        if not bot_allowed_to_scan():
            logging.info("Tarama atlandı: bot pasif veya kill switch açık")
            return

        loop_started_at = time.time()
        loop_cfg = load_config()
        scan_observation = build_scan_observation(get_active_modes(loop_cfg), symbols)
        logging.info(format_scan_observation("start", scan_observation))
        signal_message = build_signal_message(symbols, state)

        if signal_message and signal_message != state.get("last_sent_message"):
            set_last_signal(signal_message)
            append_signal_message(signal_message)

            if not is_quiet_mode():
                self.send_telegram(signal_message)
                logging.info("Yeni sinyal mesajı gönderildi")
            else:
                logging.info("Quiet mode açık; sinyal kaydedildi ama gönderilmedi")

            state["last_sent_message"] = signal_message

        if not is_quiet_mode():
            commentaries = get_daily_commentaries(symbols, state)
            for msg in commentaries:
                self.send_telegram(msg)
                logging.info("Günlük yorum gönderildi")
        else:
            logging.info("Quiet mode açık; günlük yorum gönderimi atlandı")

        finalize_pending_signals(state, fetch_klines, get_kline_limit)
        save_state(state)
        logging.info(
            "%s | duration_seconds=%.2f",
            format_scan_observation("finish", scan_observation),
            time.time() - loop_started_at,
        )

    def run_forever(self) -> None:
        state = load_state()
        self.start_telegram_command_thread()
        discovered_symbols, symbol_degraded, last_symbol_refresh = self.load_symbols_resilient()
        last_degraded_notice = time.time() if symbol_degraded else 0

        symbols = self.apply_watchlist_filter(discovered_symbols)
        logging.info("Tarama sembolleri: %s", ", ".join(symbols))
        logging.info("MarketRadarAI startup success | scan_symbol_count=%s", len(symbols))

        while True:
            try:
                self.consume_force_scan_request()
                self.poll_telegram_commands(self.send_telegram)

                discovered_symbols, symbol_degraded, last_symbol_refresh, last_degraded_notice = (
                    self.maybe_refresh_symbols(
                        discovered_symbols,
                        symbol_degraded,
                        last_symbol_refresh,
                        last_degraded_notice,
                    )
                )

                symbols = self.apply_watchlist_filter(discovered_symbols)
                self.run_scan_cycle(state, symbols)

            except Exception as e:
                logging.exception("Ana döngü hatası: %s", e)

            self.sleep_with_command_polling(next_sleep_seconds())
