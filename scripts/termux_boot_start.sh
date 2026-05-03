#!/data/data/com.termux/files/usr/bin/bash

termux-wake-lock

PROJECT_DIR="/data/data/com.termux/files/home/alarm_bot"

cd "$PROJECT_DIR" || exit 1

if [ -d "venv" ]; then
  source venv/bin/activate
fi

nohup python main.py >> logs/boot.out 2>&1 &
