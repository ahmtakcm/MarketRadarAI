# Temiz Stabil Dağıtım Notları

Bu paket `mexc_tarama_FULL_20260428_2242.zip` temel alınarak temizlenmiştir.

Çıkarılanlar:
- `venv/`
- `__pycache__/` ve bytecode dosyaları
- çalışma log/state geçmişleri
- `telegram_offset.txt`
- runtime lock/cache dosyaları

Güvenlik:
- `settings.json` içindeki Telegram token/chat bilgileri placeholder ile değiştirildi.
- Gerçek değerleri kendi ortamında `settings.json` içine gir.

Kurulum:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Not:
- Strateji dosyalarının davranışına dokunulmadı.
- Bu paket temiz başlangıç/dağıtım içindir; canlı bot geçmişi ve offset bilgisi içermez.
