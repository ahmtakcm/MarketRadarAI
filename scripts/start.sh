#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
  source venv/bin/activate
fi

python main.py >> logs/runtime.out 2>&1
