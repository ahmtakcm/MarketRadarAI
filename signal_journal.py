from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JOURNAL_PATH = DATA_DIR / "signal_journal.jsonl"
LAST_SIGNAL_PATH = DATA_DIR / "last_signal.txt"


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def parse_signal_message(message: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in str(message).splitlines() if ln.strip()]
    symbol = None
    timeframe = None
    side = None
    strategy = None

    for ln in lines:
        if re.fullmatch(r"[A-Z0-9]{2,20}USDT|XAUUSDT|XAGUSDT", ln):
            symbol = ln
            continue

        m = re.search(r"\b(1M|3M|5M|15M|30M|1H|4H|1D|1W)\s*→\s*([A-Z_]+)", ln, re.I)
        if m:
            timeframe = m.group(1).upper()
            side = m.group(2).upper()

        if ln.lower().startswith("strateji:"):
            strategy = ln.split(":", 1)[1].strip()

    return {
        "ts": now_iso(),
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "strategy": strategy,
        "raw": message,
    }


def append_signal_message(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    item = parse_signal_message(message)
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def set_last_signal(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_SIGNAL_PATH.write_text(str(message), encoding="utf-8")


def get_last_signal() -> str:
    if not LAST_SIGNAL_PATH.exists():
        return "Son sinyal kaydı yok."
    return LAST_SIGNAL_PATH.read_text(encoding="utf-8", errors="ignore")[-3500:]


def read_journal_today() -> list[dict[str, Any]]:
    if not JOURNAL_PATH.exists():
        return []

    today = dt.datetime.now().date().isoformat()
    items = []

    with JOURNAL_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if str(item.get("ts", "")).startswith(today):
                items.append(item)

    return items


def build_performance_today_text() -> str:
    items = read_journal_today()
    total = len(items)

    by_side = {}
    by_symbol = {}

    for item in items:
        side = item.get("side") or "UNKNOWN"
        symbol = item.get("symbol") or "UNKNOWN"
        by_side[side] = by_side.get(side, 0) + 1
        by_symbol[symbol] = by_symbol.get(symbol, 0) + 1

    top_symbols = sorted(by_symbol.items(), key=lambda x: x[1], reverse=True)[:5]

    lines = [
        "📊 GÜNLÜK SİNYAL RAPORU",
        "",
        f"Toplam sinyal: {total}",
        "",
        "Yön dağılımı:",
    ]

    if by_side:
        for k, v in sorted(by_side.items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- Kayıt yok")

    lines.append("")
    lines.append("En aktif semboller:")
    if top_symbols:
        for symbol, count in top_symbols:
            lines.append(f"- {symbol}: {count}")
    else:
        lines.append("- Kayıt yok")

    lines.append("")
    lines.append("Not: Bu rapor şimdilik sinyal sayım raporudur. Win-rate için entry/exit sonucu ayrıca işlenecek.")

    return "\n".join(lines)


def build_explain_last_text() -> str:
    raw = get_last_signal()
    parsed = parse_signal_message(raw)

    return (
        "🧠 SON SİNYAL TEKNİK ÖZET\n\n"
        f"Sembol: {parsed.get('symbol') or 'Bilinmiyor'}\n"
        f"Timeframe: {parsed.get('timeframe') or 'Bilinmiyor'}\n"
        f"Yön/Sinyal: {parsed.get('side') or 'Bilinmiyor'}\n"
        f"Strateji: {parsed.get('strategy') or 'Bilinmiyor'}\n\n"
        "Ham sinyal:\n"
        f"{raw[-2500:]}"
    )
