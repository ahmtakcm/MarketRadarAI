#!/data/data/com.termux/files/usr/bin/bash

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(dirname -- "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
APP_LOG="$LOG_DIR/app.log"
MAX_SIZE=$((1024 * 1024))  # 1 MB
KEEP_LINES=1000

mkdir -p "$LOG_DIR"

# Keep the last 1000 lines when app.log exceeds 1 MB.
if [ -f "$APP_LOG" ]; then
  size=$(wc -c < "$APP_LOG")
  if [ "$size" -gt "$MAX_SIZE" ]; then
    tail -n "$KEEP_LINES" "$APP_LOG" > "$APP_LOG.tmp" && mv "$APP_LOG.tmp" "$APP_LOG"
  fi
fi

# Delete temporary log backups older than seven days.
find "$LOG_DIR" -type f \( -name "*.old" -o -name "*.bak" -o -name "*.tmp" \) -mtime +7 -delete 2>/dev/null
