# MEXC Tarama Bot Altin Kurallari

Bu dokuman projede degisiklik yaparken uyulacak pratik muhendislik kurallarini tanimlar. Amac botun canli calisma guvenligini, Telegram komut stabilitesini ve deploy disiplinini korumaktir.

## 1. Canli Davranisi Korumadan Refactor Yapma

- Refactor adimlari kucuk olmalidir.
- Her adim tek sorumlulugu tasimalidir.
- Davranis degistiren islerle dosya tasima/refactor ayni committe karistirilmamalidir.
- Refactor sonrasi en az `py_compile`, `smoke_check.py`, `ops_check.py` calismalidir.

## 2. Tek Polling Owner Kuralini Bozma

- `telegram_remote.py` tek Telegram `getUpdates` sahibidir.
- `main.py` icine `getUpdates`, polling loop veya command listener eklenmez.
- `notifiers/telegram_notifier.py` sadece mesaj gonderir; polling yapmaz.
- 409 Conflict gorulurse ilk kontrol cift polling/process olmalidir.

## 3. Tek Scanner Kuralini Koru

- Canli ortamda sadece bir `main.py` calismalidir.
- Eski `RiskRadarAI/main.py` process'i asla aktif kalmamalidir.
- Eski `riskradarai.service` masked kalmalidir.
- Deploy sonrasi standart kontrol:

```bash
python scripts/ops_check.py
```

## 4. Runtime Config Git'e Girmez

Asagidaki dosya ve dizinler runtime/local durumdur, commit edilmez:

- `remote_config.json`
- `settings.json`
- `.env`
- `logs/`
- `storage/`
- `venv/`
- backup/broken dosyalari

`remote_config.json` VPS'te modified kalabilir. Bu normaldir.

## 5. Watchlist-First Mimariyi Koru

- Runtime tarama sembolleri once `remote_config.watchlist.symbols` listesinden gelir.
- Sonra `settings.json symbols`, sonra `BTCUSDT, ETHUSDT` fallback kullanilir.
- Runtime path'te tum MEXC futures listesini tarama kaynagi olarak cekme.
- `storage/last_active_symbols.json` runtime sembol kaynagi degildir.

## 6. Exchange Adapter Sozlesmesini Bozma

- `core/exchange_client.py` icindeki `fetch_klines` candle dict formatini koru:
  - `open_time`
  - `close_time`
  - `time`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
- `get_kline_limit()` EMA244 ihtiyaci nedeniyle 300 candle dondurmelidir.
- `validate_futures_symbol()` tek sembol dogrular; tum listeyi runtime'da cekmez.

## 7. Telegram Yetki Ayrimini Net Tut

- Grup/allowed chat id: komut yazilabilecek chat veya grup.
- Admin user id: admin komutu tetikleyebilecek kullanici.
- Admin komutlari gruptan tetiklenebilir, sonuc adminin ozel sohbetine gider.
- Admin ozel cevap davranisi bozulmadan refactor yapilmalidir.

## 8. Guvenlik ve Secret Hijyeni

- Token, `.env`, gercek chat id listeleri ve runtime config commit edilmez.
- Loglarda secret basilmamalidir.
- Yetkisiz mesajlar sessiz veya kontrollu sekilde reddedilmelidir.
- Admin komutlarinda kullanici id kontrolu chat id kontrolunden ayri dusunulmelidir.

## 9. Test ve Deploy Sirasi

Kod degisikligi sonrasi minimum lokal kontrol:

```bash
python -m py_compile telegram/router.py telegram/read_commands.py telegram/watchlist_commands.py telegram_commands.py telegram_remote.py scripts/smoke_check.py scripts/ops_check.py
```

VPS deploy sirasi:

```bash
git pull --ff-only origin codex/mexc-telegram-cleanup
python -m py_compile telegram/router.py telegram/read_commands.py telegram/watchlist_commands.py telegram_commands.py telegram_remote.py scripts/smoke_check.py scripts/ops_check.py
python scripts/smoke_check.py
python scripts/smoke_check.py --live
python scripts/ops_check.py
sudo systemctl restart mexc-telegram-commands.service
sudo systemctl restart mexc-tarama-bot.service
python scripts/ops_check.py
```

## 10. Rollback Hazirligi

- Stabil yedek branch korunur: `codex/backup-mexc-clean-state-20260503`.
- Buyuk davranis degisiklikleri once aktif branchte gozlenir.
- Main merge/PR karari canli gozlemden sonra verilir.
- Rollback gerekirse once servisler durumu, sonra git branch/commit durumu netlestirilir.

## 11. Gozlemlenebilirlik Once Gelir

- Her yeni operasyonel risk icin once kontrol/rapor mekanizmasi eklenmelidir.
- `/health`, `/error_log`, `scripts/smoke_check.py` ve `scripts/ops_check.py` proje saglik sinyalleridir.
- Yeni ozellikler bu sinyalleri bozmamalidir.

## 12. Sinyal Kalitesi Korunur

- Duplicate sinyal riski her davranis degisikliginde dusunulmelidir.
- Dedupe anahtari gerekirse su seviyeye guclendirilmelidir:

```text
symbol + mode + timeframe + close_time + strategy + direction
```

- Restart sonrasi ayni mum icin tekrar sinyal gonderme riski test edilmeden sinyal akisi degistirilmemelidir.

## 13. En Dusuk Riskli Siralama

Bu projede genel is onceligi:

1. Canli stabilite ve tek process/polling garantisi.
2. Test ve ops kontrolleri.
3. Moduler refactor.
4. Health ve observability iyilestirmeleri.
5. Duplicate signal dedupe.
6. Watchlist kalite filtresi.
7. Admin auth sadelestirme.
8. Main branch merge/PR.

## Kisa Ilke

Calisan bot once korunur. Her degisiklik kucuk, geri alinabilir, test edilebilir ve deploy sonrasi gozlemlenebilir olmalidir.
