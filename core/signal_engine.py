from config import ENABLED_STRATEGIES, STRATEGY_SETTINGS
from strategies import custom_strategy, ema_cross, fibb_bands, fibb_strategy, rsi_reversal

STRATEGY_MAP = {
    "custom_strategy": custom_strategy,
    "fibb_strategy": fibb_strategy,
    "fibb_bands": fibb_bands,
    "ema_cross": ema_cross,
    "rsi_reversal": rsi_reversal,
}

DISPLAY_NAMES = {
    "fibb_bands": "FiBB Bands",
    "fibb_strategy": "FIBB_STRATEGY",
}


def _normalize_strategy_output(name, output):
    display_name = DISPLAY_NAMES.get(name, name)

    if isinstance(output, tuple):
        signal, reason = output
        if not signal:
            return []
        return [{
            "strategy": display_name,
            "strategy_key": name,
            "candidate_type": "trade",
            "signal": signal,
            "reason": reason,
        }]

    if isinstance(output, dict):
        output = [output]

    if not isinstance(output, list):
        return []

    results = []
    for item in output:
        if not isinstance(item, dict) or not item.get("signal"):
            continue
        normalized = {
            "strategy": display_name,
            "strategy_key": name,
            "candidate_type": item.get("candidate_type", "trade"),
            "signal": item.get("signal"),
            "reason": item.get("reason", ""),
        }
        for key in ("phase", "score", "quality", "stop_loss"):
            if key in item:
                normalized[key] = item[key]
        results.append(normalized)

    return results


def generate_signals(context):
    """
    Aktif stratejilerin tamamını çalıştırır.
    Her strateji ihtiyaç duyduğu indikatörü core.indicators üzerinden kendisi hesaplar.
    """
    results = []

    for name in ENABLED_STRATEGIES:
        module = STRATEGY_MAP.get(name)
        if not module:
            continue

        settings = STRATEGY_SETTINGS.get(name, {})
        if settings.get("enabled") is False:
            continue

        results.extend(_normalize_strategy_output(name, module.evaluate(context, settings)))

    return results


def build_daily_commentary(symbol, levels):
    close = levels["close"]
    ema8 = levels["ema8"]
    ema21 = levels["ema21"]
    ema89 = levels["ema89"]
    ema244 = levels["ema244"]
    center = levels["center"]
    high = levels["high"]
    low = levels["low"]

    upper_fib3 = levels["upper_fib3"]
    lower_fib3 = levels["lower_fib3"]
    upper_fib4 = levels["upper_fib4"]
    lower_fib4 = levels["lower_fib4"]

    bullish = ema8 > ema21 > ema89 > ema244
    bearish = ema8 < ema21 < ema89 < ema244

    if high >= upper_fib4:
        comment = "Piyasa aşırı şişmiş durumda. Sert yükseliş sonrası yorulma ve geri çekilme riski çok yüksek."
    elif low <= lower_fib4:
        comment = "Piyasa aşırı baskı altında. Sert satış sonrası tepki yükselişi gelme ihtimali artıyor."
    elif close >= upper_fib3:
        comment = "Fiyat güçlü genişleme bölgesinde. Trend devam ediyor ama artık dikkatli olmak gerekiyor."
    elif close <= lower_fib3:
        comment = "Fiyat baskı bölgesinde. Düşüş devam ediyor ama tepki ihtimali oluşmaya başladı."
    elif bullish and close > center:
        comment = "Trend net yukarı. Alıcılar kontrolü elinde tutuyor, geri çekilmeler alım fırsatı olabilir."
    elif bearish and close < center:
        comment = "Trend net aşağı. Satıcılar baskın, yükselişler satış fırsatı gibi çalışabilir."
    elif close > center:
        comment = "Fiyat merkez üstünde tutunuyor. Yukarı yön denemesi var ama henüz güçlü trend yok."
    elif close < center:
        comment = "Fiyat merkez altında. Zayıf görünüm devam ediyor, yön aşağı ağırlıklı."
    else:
        comment = "Piyasa kararsız. Net yön yok, beklemek daha sağlıklı olabilir."

    return (
        f"📊 GÜNLÜK DURUM | 1D\n\n"
        f"🪙 {symbol}\n"
        f"💰 Fiyat: {close}\n"
        f"🎯 Merkez (1D): {center:.2f}\n\n"
        f"🧠 Yorum:\n{comment}"
    )
