#!/bin/sh
# Start the app and open it in the browser. In Git Bash (Windows) or a terminal (macOS/Linux):
#   ./start.sh            this computer only (stop it with Ctrl+C)
#   ./start.sh phone      also reachable from your phone on the same Wi-Fi (or over Tailscale): prints the address
cd "$(dirname "$0")" || exit 1
if [ -x .venv/Scripts/python ] || [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else echo "No .venv found: run the install steps in README.md first."; exit 1; fi
PORT=8000
HOST=127.0.0.1
if [ "$1" = "phone" ]; then
  HOST=0.0.0.0
  # the address this computer uses on the local network (nothing is sent: a UDP socket only picks the route)
  LAN=$("$PY" -c "import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(('10.255.255.255', 1)); print(s.getsockname()[0])
except OSError:
    pass
finally:
    s.close()" 2>/dev/null)
  TS=""
  if command -v tailscale >/dev/null 2>&1; then TS=$(tailscale ip -4 2>/dev/null | head -n 1); fi
  echo ""
  echo "Phone mode: the app accepts connections from other devices on your network."
  if [ -n "$LAN" ] && [ "${LAN#127.}" = "$LAN" ]; then
    echo "  On your phone, on the same Wi-Fi, open:   http://$LAN:$PORT"
  else
    echo "  Could not tell this computer's network address: run ipconfig (Windows) or ifconfig and use its IPv4 address."
  fi
  if [ -n "$TS" ]; then
    echo "  From anywhere, with Tailscale on the phone: http://$TS:$PORT"
  fi
  echo "  If Windows asks about the firewall, allow Python on Private networks only."
  echo "  Use this only on your own Wi-Fi (or Tailscale), never on public Wi-Fi: the app has no login."
  echo ""
fi
URL=http://localhost:$PORT
( sleep 4
  if command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start "" "$URL" >/dev/null 2>&1
  elif command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1
  fi ) &
echo "Starting Astro Football Lab on $URL  (Ctrl+C to stop)"
exec "$PY" -m uvicorn astrofoot.web.app:app --host "$HOST" --port "$PORT"
