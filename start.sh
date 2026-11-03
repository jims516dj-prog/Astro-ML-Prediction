#!/bin/sh
# Start the app and open it in the browser. In Git Bash (Windows) or a terminal (macOS/Linux):
#   ./start.sh            (stop it with Ctrl+C)
cd "$(dirname "$0")" || exit 1
if [ -x .venv/Scripts/python ] || [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else echo "No .venv found: run the install steps in README.md first."; exit 1; fi
URL=http://localhost:8000
( sleep 4
  if command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start "" "$URL" >/dev/null 2>&1
  elif command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1
  fi ) &
echo "Starting Astro Football Lab on $URL  (Ctrl+C to stop)"
exec "$PY" -m uvicorn astrofoot.web.app:app --port 8000
