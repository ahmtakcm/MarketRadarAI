# MEXC Tarama Bot Runbook

Bu dokuman `mexc-tarama-bot` projesinin calisan sunucu durumunu, deploy akisini ve sorun giderme notlarini ozetler. Secret, token, gercek `.env` degeri veya runtime config icermez.

## Aktif Durum

- GitHub repo: `ahmtakcm/mexc-tarama-bot`
- Aktif branch: `codex/mexc-telegram-cleanup`
- Stabil yedek branch: `codex/backup-mexc-clean-state-20260503`
- VPS dizini: `~/mexc-tarama-bot`
- Ana bot servisi: `mexc-tarama-bot.service`
- Telegram komut servisi: `mexc-telegram-commands.service`
- Eski `riskradarai.service` kapali ve disabled olmalidir.

## Mimari

Ana bot ve Telegram komut dinleyici ayridir.

Proje genel muhendislik kurallari icin `PROJECT_GOLDEN_RULES.md` dosyasina bakilmalidir.

- `main.py`
  - Sadece tarama, sinyal uretimi, gunluk yorum ve lifecycle bildirimi yapar.
  - `getUpdates` veya command polling calistirmaz.

- `telegram_remote.py`
  - Tek Telegram polling owner'dir.
  - `TELEGRAM_COMMANDS_ENABLED=1` veya remote config ile acilir.
  - `telegram_commands.poll_telegram_commands()` calistirir.

- `notifiers/telegram_notifier.py`
  - Sadece `sendMessage` kullanir.
  - Parametresiz cagri notification chat'e gider.
  - Komut cevaplarinda `chat_id` verilirse cevap komut hedef chat'ine gider.

- `core/symbol_runtime.py`
  - Runtime sembol kaynagini belirler.
  - Once `remote_config.watchlist.symbols`, sonra `settings.json symbols`, sonra `BTCUSDT, ETHUSDT` fallback kullanilir.

- `core/exchange_client.py`
  - MEXC futures adapter.
  - `fetch_klines` dict candle formatini korur: `open_time`, `close_time`, `time`, `open`, `high`, `low`, `close`, `volume`.
  - `validate_futures_symbol()` tek sembol dogrulama yapar; tum futures listesini runtime path'te cekmez.

## Watchlist Runtime

Runtime tum MEXC futures listesini tarama kaynagi olarak kullanmaz.

Sembol secim sirasi:

1. `remote_config.json` icindeki `watchlist.symbols`
2. `settings.json` icindeki `symbols`
3. Hardcoded fallback: `BTCUSDT`, `ETHUSDT`

Sembol dogrulama:

- Sembol normalize edilir.
- Sadece USDT futures sembolleri kabul edilir.
- Tek sembol `ticker` dogrulanir.
- Tek sembol `kline` yeterliligi kontrol edilir.
- Gecersiz sembol loglanir ve tarama disinda kalir.

## Telegram Komut Modeli

Komutlar gruptan veya ozel sohbetten gelebilir.

- Read-only ve watchlist komutlari komutun geldigi chat'e cevap verir.
- Admin kontrol komutlari gruptan tetiklenebilir, fakat sonuc yetkili adminin ozel sohbetine gider.
- Admin sonucunu ozelden gonderebilmek icin adminin botla ozelde `/start` yapmis olmasi gerekir.
- Yetki kontrolu `remote_config.json` icindeki Telegram admin/allowed id listeleri ve config fallback'leri ile yapilir.

Desteklenen genel komutlar:

```text
/help
/ping
/status
/health
/watchlist
/symbols
/addsymbol
/add_symbol
/watch
/removesymbol
/remove_symbol
/unwatch
/scan_now
/last_signal
/explain_last
/performance_today
/modes
/filters
/log
/error_log
/botfather_commands
```

Admin komutlari:

```text
/start_bot
/stop_bot
/quiet_on
/quiet_off
/kill_switch_on
/kill_switch_off
/scalp_on
/scalp_off
/intraday_on
/intraday_off
/midterm_on
/midterm_off
/mode_only
/fake_filter_on
/fake_filter_off
/volume_filter_on
/volume_filter_off
/explain_on
/explain_off
```

## Telegram Menu Sync

BotFather menusu `BOTFATHER_COMMANDS.txt` ile uyumlu tutulur.

Komut menusunu Telegram API'ye basmak icin:

```bash
cd ~/mexc-tarama-bot
python scripts/set_bot_commands.py --scope all
```

Sadece grup menusu icin:

```bash
python scripts/set_bot_commands.py --scope group
```

Bu script `setMyCommands` kullanir, `getUpdates` kullanmaz.

## Deploy / Update

VPS uzerinde guncelleme:

```bash
cd ~/mexc-tarama-bot
git pull --ff-only origin codex/mexc-telegram-cleanup

python -m py_compile main.py
python -m py_compile config.py
python -m py_compile telegram_commands.py
python -m py_compile telegram_remote.py
python -m py_compile notifiers/telegram_notifier.py
python -m py_compile core/exchange_client.py
python -m py_compile remote_config.py

sudo systemctl restart mexc-tarama-bot.service
sudo systemctl restart mexc-telegram-commands.service
```

Canli smoke check:

```bash
python scripts/smoke_check.py --live
```

Beklenen ornek:

```text
validate_BTCUSDT=True reason=ok
candle_shape=True reason=ok count=300/300
levels_ready=True
```

Operasyon kontrolu:

```bash
python scripts/ops_check.py
```

Beklenen:

```text
OK required_files: ok
OK git_unexpected_changes: none
OK old_riskradarai_process: count=0
OK main_process: count=1
OK telegram_remote_process: count=1
OK mexc-tarama-bot.service_active: active
OK mexc-tarama-bot.service_enabled: enabled
OK mexc-telegram-commands.service_active: active
OK mexc-telegram-commands.service_enabled: enabled
OK riskradarai.service_active: inactive
OK riskradarai.service_enabled: disabled veya not-found
ops_check=ok
```

## Servis Kontrolu

Durum:

```bash
sudo systemctl status mexc-tarama-bot.service --no-pager
sudo systemctl status mexc-telegram-commands.service --no-pager
```

Otomatik baslama:

```bash
sudo systemctl is-enabled mexc-tarama-bot.service
sudo systemctl is-enabled mexc-telegram-commands.service
```

Beklenen:

```text
enabled
enabled
```

Process kontrolu:

```bash
ps aux | grep -E "RiskRadarAI|telegram_remote.py|main.py" | grep -v grep
```

Beklenen sadece iki process:

```text
.../mexc-tarama-bot/.../main.py
.../mexc-tarama-bot/.../telegram_remote.py
```

## Log Kontrolu

Ana bot logu:

```bash
tail -n 80 logs/app.log
```

Telegram command stderr:

```bash
tail -n 80 storage/telegram_commands.err
```

Son restart dogrulama:

```bash
grep "Bot basladi" logs/app.log | tail
```

Beklenen startup satirlari:

```text
Bot basladi
Watchlist sembolleri: ... | kaynak=remote_config.watchlist.symbols
Watchlist dogrulandi: ... | gecersiz=0 | kaynak=remote_config.watchlist.symbols
Tarama sembolleri: ...
```

## Sorun Giderme

### 409 Conflict

Belirti:

```text
Conflict: terminated by other getUpdates request
```

Sebep: Ayni bot token ile ikinci bir `getUpdates` client calisiyordur.

Kontrol:

```bash
ps aux | grep -E "RiskRadarAI|telegram_remote.py|main.py" | grep -v grep
sudo systemctl list-units --all | grep -Ei "risk|mexc|telegram|bot"
```

Beklenen:

- Eski `riskradarai.service` kapali olmalidir.
- Sadece bir `telegram_remote.py` calismalidir.
- `main.py` bir kez calismalidir.

### Yetkisiz Telegram Mesaji

Belirti:

```text
Yetkisiz Telegram mesaji reddedildi: chat_id=...
```

Cozum:

- Chat/user id dogru admin/allowed listeye eklenmelidir.
- Runtime config sunucuda `remote_config.json` icindedir ve GitHub'a commit edilmemelidir.

### Admin Komutu Gruptan Cevap Vermiyor

Beklenen davranis: Admin komutu gruptan yazilirsa sonuc adminin ozel sohbetine gider.

Cevap gelmezse:

1. Admin botla ozel sohbette `/start` yapmali.
2. `storage/telegram_commands.err` kontrol edilmeli.
3. Admin `from.id` degeri admin user id listesinde olmalidir.

### Cift Scanner

Belirti: Process listesinde iki `main.py` gorulur.

Cozum: Manuel calisan process oldurulur, systemd process birakilir.

```bash
kill <manuel_pid>
ps aux | grep -E "telegram_remote.py|main.py" | grep -v grep
```

## GitHub / Backup

Calisan temiz durum icin yedek branch:

```text
codex/backup-mexc-clean-state-20260503
```

Runtime dosyalari GitHub'a alinmaz:

- `remote_config.json`
- `settings.json`
- `.env`
- `logs/`
- `storage/`
- `venv/`
- backup/broken dosyalari

## Notlar

- `core/indicator_engine.py` borsa bagimsiz hesap motoru olarak kalir.
- `fetch_klines` candle dict formatini bozma.
- Runtime path'te tum MEXC futures listesini cekme.
- Manuel `getUpdates` calistirma; command service acikken 409 riskini geri getirir.
