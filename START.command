#!/bin/bash
# Personal AI OS — one-click launcher (macOS).
# Double-click this file in Finder. It starts the engine + control server
# and opens the dashboard in your browser.
cd "$(dirname "$0")" || exit 1

# Pick the project virtualenv python if it exists, else system python3.
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
else
  PY="python3"
fi

# Open the dashboard a moment after the server starts.
( sleep 2; open "http://localhost:8800" ) &

echo "Starting Personal AI OS… (close this window to stop everything)"
exec "$PY" control_server.py
