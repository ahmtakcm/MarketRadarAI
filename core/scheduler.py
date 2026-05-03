import datetime as dt

from config import MODE_TIMEFRAMES
from remote_config import load_config


def tf_to_seconds(tf: str) -> int:
    tf = str(tf).strip().lower()

    if tf.endswith("m"):
        return int(tf[:-1]) * 60

    if tf.endswith("h"):
        return int(tf[:-1]) * 3600

    if tf.endswith("d"):
        return int(tf[:-1]) * 86400

    return 60


def seconds_to_next_close(tf: str) -> int:
    now = dt.datetime.utcnow()
    tf_seconds = tf_to_seconds(tf)
    epoch = int(now.timestamp())

    wait = tf_seconds - (epoch % tf_seconds)

    # Tam kapanış anında çok kısa bekleyip borsanın mumu finalize etmesine izin ver.
    if wait <= 1:
        return 3

    return wait + 2


def get_active_modes():
    cfg = load_config()
    modes = cfg.get("modes", {})
    mode_only = cfg.get("mode_only")

    if mode_only and mode_only != "off":
        return [mode_only] if modes.get(mode_only) else []

    active = []
    for mode in ["scalp", "intraday", "midterm"]:
        if modes.get(mode):
            active.append(mode)

    return active


def get_active_mode_plans():
    plans = []
    for mode in get_active_modes():
        plan = MODE_TIMEFRAMES.get(mode)
        if not plan:
            continue

        plans.append({
            "mode": mode,
            "label": plan.get("label", mode),
            "bias": plan["bias"],
            "setup": plan["setup"],
            "entry": plan["entry"],
        })

    return plans


def get_active_timeframes():
    """
    Eski scanner uyumluluğu için entry timeframe listesi döndürür.
    Yeni mimaride ana zamanlama entry mum kapanışına göre yapılır.
    """
    return sorted({plan["entry"] for plan in get_active_mode_plans()})


def next_sleep_seconds():
    plans = get_active_mode_plans()

    if not plans:
        return 30

    waits = [seconds_to_next_close(plan["entry"]) for plan in plans]
    return max(5, min(waits))


def build_schedule_text():
    plans = get_active_mode_plans()

    if not plans:
        return "⏱️ TARAYICI PLANI\n\nAktif mod yok."

    lines = ["⏱️ TARAYICI PLANI", ""]

    for plan in plans:
        wait = seconds_to_next_close(plan["entry"])
        lines.append(
            f"{plan['label']} ({plan['mode']})\n"
            f"Bias: {plan['bias']} | Setup: {plan['setup']} | Entry: {plan['entry']}\n"
            f"Sonraki entry kapanışı: yaklaşık {wait} sn"
        )
        lines.append("")

    lines.append("Not: Tarama entry mum kapanışında yapılır; bias ve setup verileri analiz için çekilir.")
    return "\n".join(lines).strip()
