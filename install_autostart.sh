#!/usr/bin/env bash
# install_autostart.sh — run Personal-AI-OS control_server.py automatically on
# login (macOS LaunchAgent). Re-run this from the project folder after moving it
# to a new path to re-point the agent. Pass `uninstall` to remove it.
#
#   ./install_autostart.sh            # install + start now + on every login
#   ./install_autostart.sh uninstall  # stop + remove
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # the Personal-AI-OS dir
LABEL="com.anchit.personal-ai-os"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "uninstall" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed autostart ($LABEL)."
  exit 0
fi

# Prefer the reinstalled .venv, fall back to venv.
PY="$HERE/.venv/bin/python"; [ -x "$PY" ] || PY="$HERE/venv/bin/python"
[ -x "$PY" ] || { echo "No venv python found at $HERE/.venv or $HERE/venv"; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents" "$HERE/logs"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$HERE/control_server.py</string>
  </array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HERE/logs/control_server.out.log</string>
  <key>StandardErrorPath</key><string>$HERE/logs/control_server.err.log</string>
</dict></plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed $LABEL"
echo "  python : $PY"
echo "  script : $HERE/control_server.py"
echo "  dashboard once up: http://localhost:8800"
echo "  logs   : $HERE/logs/control_server.{out,err}.log"
echo "  uninstall: ./install_autostart.sh uninstall"
