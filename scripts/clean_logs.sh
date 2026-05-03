#!/data/data/com.termux/files/usr/bin/bash

LOG_DIR="$HOME/mexc_tarama/logs"
APP_LOG="$LOG_DIR/app.log"
MAX_SIZE=$((1024 * 1024))   # 1 MB
KEEP_LINES=1000

mkdir -p "$LOG_DIR"

# app.log 1 MB üstüne çıkarsa son 1000 satırı bırak
if [ -f "$APP_LOG" ]; then
  size=$(wc -c < "$APP_LOG")
  if [ "$size" -gt "$MAX_SIZE" ]; then
    tail -n "$KEEP_LINES" "$APP_LOG" > "$APP_LOG.tmp" && mv "$APP_LOG.tmp" "$APP_LOG"
  fi
fi

# 7 günden eski geçici/yedek logları sil
find "$LOG_DIR" -type f \( -name "*.old" -o -name "*.bak" -o -name "*.tmp" \) -mtime +7 -delete 2>/dev/null
