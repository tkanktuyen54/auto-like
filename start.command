#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  task_python=""
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
      task_python="$candidate"
      break
    fi
  done
  if [ -z "$task_python" ]; then
    echo "Can cai Python 3.11 tro len tu https://www.python.org/downloads/"
    read -r -p "Nhan Enter de dong..." unused
    exit 1
  fi
  "$task_python" -m venv .venv
fi
if ! .venv/bin/python -c 'import autoclap, telethon, PySide6' >/dev/null 2>&1; then
  .venv/bin/python -m ensurepip --upgrade
  .venv/bin/python -m pip install -e .
fi
exec .venv/bin/python -m autoclap
