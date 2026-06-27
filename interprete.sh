#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "$GEMINI_API_KEY" ]; then
  echo "Falta GEMINI_API_KEY. Crea ~/interprete/.env con GEMINI_API_KEY=... o expórtala." >&2
  exit 1
fi
brave "file://$PWD/index.html" >/dev/null 2>&1 &
exec ./venv/bin/python servidor.py
