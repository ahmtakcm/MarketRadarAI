import os, time, traceback
from pathlib import Path
import requests

from remote_config import load_config, save_config, get_active_modes
from remote_security import is_authorized
from update_manager import INBOX_DIR, apply_update, rollback

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

BASE_DIR = Path(__file__).resolve().parent
OFFSET_FILE = BASE_DIR / "telegram_offset.txt"

def tg(method, **data):
    r = requests.post(f"{API}/{method}", data=data, timeout=30)
    r.raise_for_status()
    return r.json()

def send(chat_id, text):
    tg("sendMessage", chat_id=chat_id, text=text[:3900], disable_web_page_preview=True)

def get_offset():
    try:
        return int(OFFSET_FILE.read_text().strip())
    except:
        return 0

def set_offset(v):
    OFFSET_FILE.write_text(str(v), encoding="utf-8")

def status_text():
    c = load_config()
    return (
        "ğŸ“Š BOT DURUMU\n\n"
        f"Bot aktif: {'âœ…' if c.get('bot_active') else 'âŒ'}\n"
        f"Kill switch: {'ğŸš¨ AÃ‡IK' if c.get('kill_switch') else 'âœ… KapalÄ±'}\n"
        f"Risk: {c.get('risk_level')}\n"
        f"Mode only: {c.get('mode_only') or 'Yok'}\n"
        f"Aktif modlar: {', '.join(get_active_modes(c)) or 'Yok'}\n\n"
        f"Scalp: {'âœ…' if c['modes'].get('scalp') else 'âŒ'}\n"
        f"Intraday: {'âœ…' if c['modes'].get('intraday') else 'âŒ'}\n"
        f"Midterm: {'âœ…' if c['modes'].get('midterm') else 'âŒ'}\n\n"
        f"Fake breakout: {'âœ…' if c['filters'].get('fake_breakout_filter') else 'âŒ'}\n"
        f"Volume: {'âœ…' if c['filters'].get('volume_confirmation') else 'âŒ'}\n"
    )

def handle_text(text):
    c = load_config()
    parts = text.strip().split()
    cmd = parts[0].lower() if parts else ""

    if cmd in ["/help", "/komutlar"]:
        return """ğŸ§­ KOMUTLAR

/status
/start_bot
/stop_bot
/restart

/update_zip
/update_apply
/update_status
/rollback

/scalp_on /scalp_off
/intraday_on /intraday_off
/midterm_on /midterm_off
/mode_only scalp|intraday|midterm|off

/risk low|normal|aggressive
/fake_filter_on /fake_filter_off
/volume_filter_on /volume_filter_off
/kill_switch_on /kill_switch_off
/log
"""

    if cmd == "/status":
        return status_text()

    if cmd == "/start_bot":
        c["bot_active"] = True
        save_config(c)
        return "âœ… Bot aktif edildi."

    if cmd == "/stop_bot":
        c["bot_active"] = False
        save_config(c)
        return "â¸ï¸ Bot durduruldu."

    if cmd == "/kill_switch_on":
        c["kill_switch"] = True
        save_config(c)
        return "ğŸš¨ Kill switch aÃ§Ä±ldÄ±."

    if cmd == "/kill_switch_off":
        c["kill_switch"] = False
        save_config(c)
        return "âœ… Kill switch kapatÄ±ldÄ±."

    if cmd in ["/scalp_on", "/scalp_off", "/intraday_on", "/intraday_off", "/midterm_on", "/midterm_off"]:
        mode, state = cmd.strip("/").split("_")
        c["modes"][mode] = state == "on"
        save_config(c)
        return f"âœ… {mode} {'aÃ§Ä±ldÄ±' if state == 'on' else 'kapatÄ±ldÄ±'}."

    if cmd == "/mode_only":
        if len(parts) < 2 or parts[1] not in ["scalp", "intraday", "midterm", "off"]:
            return "KullanÄ±m: /mode_only scalp|intraday|midterm|off"
        c["mode_only"] = None if parts[1] == "off" else parts[1]
        save_config(c)
        return f"âœ… Mode only: {c['mode_only'] or 'KapalÄ±'}"

    if cmd == "/risk":
        if len(parts) < 2 or parts[1] not in ["low", "normal", "aggressive"]:
            return "KullanÄ±m: /risk low|normal|aggressive"
        c["risk_level"] = parts[1]
        save_config(c)
        return f"âœ… Risk seviyesi: {parts[1]}"

    if cmd == "/fake_filter_on":
        c["filters"]["fake_breakout_filter"] = True
        save_config(c)
        return "âœ… Fake breakout filtresi aÃ§Ä±ldÄ±."

    if cmd == "/fake_filter_off":
        c["filters"]["fake_breakout_filter"] = False
        save_config(c)
        return "âš ï¸ Fake breakout filtresi kapatÄ±ldÄ±."

    if cmd == "/volume_filter_on":
        c["filters"]["volume_confirmation"] = True
        save_config(c)
        return "âœ… Volume filtresi aÃ§Ä±ldÄ±."

    if cmd == "/volume_filter_off":
        c["filters"]["volume_confirmation"] = False
        save_config(c)
        return "âš ï¸ Volume filtresi kapatÄ±ldÄ±."

    if cmd == "/update_zip":
        c["update"]["last_status"] = "waiting_zip"
        save_config(c)
        return "ğŸ“¦ ZIP bekleniyor. Åimdi ZIP dosyasÄ±nÄ± Telegramâ€™a gÃ¶nder."

    if cmd == "/update_status":
        return f"ğŸ“¦ Update durumu: {c['update'].get('last_status')}\nPending ZIP: {c['update'].get('pending_zip')}"

    if cmd == "/update_apply":
        c["bot_active"] = False
        save_config(c)
        result = apply_update()
        c = load_config()
        c["update"]["last_status"] = "applied"
        save_config(c)
        return result + "\n\nNot: Ana bot restart entegrasyonu ayrÄ±ca baÄŸlanacak."

    if cmd == "/rollback":
        return rollback()

    if cmd == "/restart":
        return "â™»ï¸ Restart komutu alÄ±ndÄ±. Servis/Task Scheduler entegrasyonu sonraki adÄ±mda baÄŸlanacak."

    if cmd == "/log":
        for p in [BASE_DIR / "logs" / "app.log", BASE_DIR / "app.log", BASE_DIR / "alarm_log.txt"]:
            if p.exists():
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()[-40:]
                return "ğŸ“œ SON LOG\n\n" + "\n".join(lines)[-3500:]
        return "Log bulunamadÄ±."

    return "Bilinmeyen komut. /help yaz."

def handle_document(msg):
    c = load_config()

    if c["update"].get("last_status") != "waiting_zip":
        return "ZIP geldi ama /update_zip modu aÃ§Ä±k deÄŸil."

    doc = msg.get("document", {})
    filename = doc.get("file_name", "")

    if not filename.lower().endswith(".zip"):
        return "Sadece .zip kabul edilir."

    file_id = doc["file_id"]
    info = tg("getFile", file_id=file_id)
    file_path = info["result"]["file_path"]

    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    target = INBOX_DIR / filename
    target.write_bytes(r.content)

    c["update"]["pending_zip"] = str(target)
    c["update"]["last_status"] = "zip_received"
    save_config(c)

    return f"âœ… ZIP alÄ±ndÄ±: {filename}\nUygulamak iÃ§in /update_apply yaz."

def run():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN yok.")

    while True:
        try:
            data = tg("getUpdates", offset=get_offset(), timeout=25)

            for upd in data.get("result", []):
                set_offset(upd["update_id"] + 1)
                msg = upd.get("message", {})
                chat_id = msg.get("chat", {}).get("id")

                if not chat_id:
                    continue

                if not is_authorized(chat_id):
                    send(chat_id, "â›” Yetkisiz eriÅŸim.")
                    continue

                if "document" in msg:
                    reply = handle_document(msg)
                else:
                    reply = handle_text(msg.get("text", ""))

                send(chat_id, reply)

        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    run()
