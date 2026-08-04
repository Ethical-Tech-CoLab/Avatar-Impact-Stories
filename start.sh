#!/usr/bin/env bash
# Starts the Many Voices kiosk and opens it in your browser.
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 tools/serve.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python tools/serve.py "$@"
fi

echo "Python 3 was not found. Install it from https://www.python.org/downloads/ and try again." >&2
exit 1
