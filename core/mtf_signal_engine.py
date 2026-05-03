def _side(levels):
    if not levels:
        return "neutral"

    close = levels.get("close")
    center = levels.get("center")

    if close is None or center is None:
        return "neutral"

    if close > center:
        return "bullish"
    if close < center:
        return "bearish"
    return "neutral"


def _signal_direction(signal):
    signal = str(signal or "").upper()
    if signal == "LONG":
        return "bullish"
    if signal == "SHORT":
        return "bearish"
    return "neutral"


def _is_fake_breakout(signal, levels):
    """
    Basit V1 fake breakout kontrolü:
    LONG sinyalde kapanış merkez üstünde olmalı.
    SHORT sinyalde kapanış merkez altında olmalı.
    Fitil ters yöne taşmış ama kapanış teyit vermemişse fake sayılır.
    """
    signal = str(signal or "").upper()

    close = levels.get("close")
    center = levels.get("center")
    high = levels.get("high")
    low = levels.get("low")

    if close is None or center is None:
        return False

    if signal == "LONG":
        return close <= center or (high is not None and high > center and close <= center)

    if signal == "SHORT":
        return close >= center or (low is not None and low < center and close >= center)

    return False


def _volume_ok(levels):
    """
    V1 volume filtresi:
    indicator_engine levels içinde volume bilgisi varsa kontrol eder.
    Yoksa filtreyi geçer, çünkü mevcut veri yapısında hacim olmayabilir.
    """
    volume = levels.get("volume")
    avg_volume = levels.get("avg_volume") or levels.get("volume_ma")

    if volume is None or avg_volume is None:
        return True, "hacim verisi yok; filtre pas geçti"

    try:
        volume = float(volume)
        avg_volume = float(avg_volume)
    except Exception:
        return True, "hacim okunamadı; filtre pas geçti"

    if avg_volume <= 0:
        return True, "ortalama hacim geçersiz; filtre pas geçti"

    ratio = volume / avg_volume

    if ratio >= 1.05:
        return True, f"hacim onaylı ({ratio:.2f}x)"

    return False, f"hacim zayıf ({ratio:.2f}x)"


def analyze_mtf_signal(sig, bias_levels, setup_levels, entry_levels, plan, cfg=None):
    cfg = cfg or {}

    filters = cfg.get("filters", {})
    fake_filter = bool(filters.get("fake_breakout_filter"))
    volume_filter = bool(filters.get("volume_confirmation"))

    signal = str(sig.get("signal", "")).upper()
    direction = _signal_direction(signal)

    bias_side = _side(bias_levels)
    setup_side = _side(setup_levels)
    entry_side = _side(entry_levels)

    if direction == "neutral":
        return {
            "allowed": False,
            "score": 0,
            "quality": "PASS",
            "reason": "LONG/SHORT dışı sinyal trade sinyali olarak kullanılmadı.",
            "bias_side": bias_side,
            "setup_side": setup_side,
            "entry_side": entry_side,
        }

    score = 40
    notes = []

    if bias_side == direction:
        score += 30
        notes.append("bias uyumlu")
    else:
        notes.append("bias uyumsuz")

    if setup_side == direction:
        score += 20
        notes.append("setup uyumlu")
    else:
        notes.append("setup uyumsuz")

    if entry_side == direction:
        score += 10
        notes.append("entry uyumlu")
    else:
        notes.append("entry uyumsuz")

    allowed = bias_side == direction and setup_side == direction and entry_side == direction

    if fake_filter:
        if _is_fake_breakout(signal, entry_levels):
            allowed = False
            score -= 25
            notes.append("fake breakout şüphesi")
        else:
            score += 5
            notes.append("fake breakout filtresi geçti")

    if volume_filter:
        vol_ok, vol_note = _volume_ok(entry_levels)
        notes.append(vol_note)
        if vol_ok:
            score += 5
        else:
            allowed = False
            score -= 20

    score = max(0, min(100, score))

    # Patch-10D:
    # EXTREME kalite artık sadece strateji sinyali gerçekten EXTREME_* ise verilir.
    # Normal LONG/SHORT, MTF tam uyumlu olsa bile en fazla HIGH olabilir.
    is_strategy_extreme = str(signal).startswith("EXTREME_")

    if is_strategy_extreme and score >= 90:
        quality = "EXTREME"
    elif score >= 70:
        quality = "HIGH"
        if not is_strategy_extreme and score > 89:
            score = 89
    elif score >= 55:
        quality = "MEDIUM"
    else:
        quality = "LOW"

    return {
        "allowed": allowed,
        "score": score,
        "quality": quality,
        "reason": ", ".join(notes),
        "bias_side": bias_side,
        "setup_side": setup_side,
        "entry_side": entry_side,
    }


def build_mtf_context(plan, mtf):
    return (
        f"Mod: {plan['label']} ({plan['mode']})\n"
        f"Zaman Yapısı: Bias {plan['bias']} | Setup {plan['setup']} | Entry {plan['entry']}\n"
        f"Bias: {mtf['bias_side']}\n"
        f"Setup: {mtf['setup_side']}\n"
        f"Entry: {mtf['entry_side']}\n"
        f"Güç: {mtf['quality']} | Skor: {mtf['score']}/100"
    )
