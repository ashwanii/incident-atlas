#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  python3 -c 'import secrets; from pathlib import Path; Path(".env").write_text("API_KEY="+secrets.token_urlsafe(32)+"\nADMIN_KEY="+secrets.token_urlsafe(32)+"\n")'
  chmod 600 .env
fi
docker compose up --build -d
printf '\nOpen http://localhost:8000. Access keys are in .env.\n'
