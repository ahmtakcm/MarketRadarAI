from __future__ import annotations

SUPPORTED_COMMANDS = {
    "/start": "Baslangic ve komut ozeti",
    "/help": "Komut listesini goster",
    "/ping": "Baglanti testi",
    "/status": "Bot durumunu goster",
    "/health": "Sistem saglik ozeti",
    "/watchlist": "Watchlist ve sembol durumlari",
    "/symbols": "Watchlist ve sembol durumlari",
    "/addsymbol": "Watchlist'e sembol ekle",
    "/add_symbol": "Watchlist'e sembol ekle",
    "/watch": "Watchlist'e sembol ekle",
    "/removesymbol": "Watchlist'ten sembol sil",
    "/remove_symbol": "Watchlist'ten sembol sil",
    "/unwatch": "Watchlist'ten sembol sil",
    "/scan_now": "Bir sonraki dongude tarama iste",
    "/last_signal": "Son sinyali goster",
    "/explain_last": "Son sinyalin teknik ozetini goster",
    "/performance_today": "Gunluk sinyal sayim raporu",
    "/modes": "Aktif modlari goster",
    "/filters": "Filtre ayarlarini goster",
    "/log": "Son uygulama loglarini goster",
    "/error_log": "Son hata/uyari loglarini goster",
    "/botfather_commands": "BotFather menu komutlarini goster",
    "/start_bot": "ADMIN: Botu aktif et",
    "/stop_bot": "ADMIN: Botu pasife al",
    "/quiet_on": "ADMIN: Sessiz modu ac",
    "/quiet_off": "ADMIN: Sessiz modu kapat",
    "/kill_switch_on": "ADMIN: Acil sinyal kesmeyi ac",
    "/kill_switch_off": "ADMIN: Acil sinyal kesmeyi kapat",
    "/scalp_on": "ADMIN: Scalp modunu ac",
    "/scalp_off": "ADMIN: Scalp modunu kapat",
    "/intraday_on": "ADMIN: Intraday modunu ac",
    "/intraday_off": "ADMIN: Intraday modunu kapat",
    "/midterm_on": "ADMIN: Midterm modunu ac",
    "/midterm_off": "ADMIN: Midterm modunu kapat",
    "/mode_only": "ADMIN: Tek mod sec veya off yap",
    "/fake_filter_on": "ADMIN: Fake breakout filtresini ac",
    "/fake_filter_off": "ADMIN: Fake breakout filtresini kapat",
    "/volume_filter_on": "ADMIN: Hacim filtresini ac",
    "/volume_filter_off": "ADMIN: Hacim filtresini kapat",
    "/explain_on": "ADMIN: Sinyal aciklamalarini ac",
    "/explain_off": "ADMIN: Sinyal aciklamalarini kapat",
}

ADD_SYMBOL_COMMANDS = {"/addsymbol", "/add_symbol", "/watch"}
REMOVE_SYMBOL_COMMANDS = {"/removesymbol", "/remove_symbol", "/unwatch"}
WATCHLIST_COMMANDS = {"/symbols", "/watchlist"}
GROUP_PUBLIC_COMMANDS = {
    "/start",
    "/help",
    "/watchlist",
    "/symbols",
    "/last_signal",
    "/performance_today",
}
PRIVATE_ADMIN_COMMANDS = {
    "/start_bot",
    "/stop_bot",
    "/quiet_on",
    "/quiet_off",
    "/kill_switch_on",
    "/kill_switch_off",
    "/scalp_on",
    "/scalp_off",
    "/intraday_on",
    "/intraday_off",
    "/midterm_on",
    "/midterm_off",
    "/mode_only",
    "/fake_filter_on",
    "/fake_filter_off",
    "/volume_filter_on",
    "/volume_filter_off",
    "/explain_on",
    "/explain_off",
}


def command_name(text: str) -> str:
    token = str(text or "").split()[0].lower()
    if "@" in token:
        token = token.split("@", 1)[0]
    return token


def command_args(text: str) -> list[str]:
    return str(text or "").split()[1:]
