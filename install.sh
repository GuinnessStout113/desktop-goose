#!/bin/bash
# Install Desktop Goose from source on macOS and start it at every login.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
L=local.desktop-goose
P="$HOME/Library/LaunchAgents/$L.plist"

command -v python3 >/dev/null || { echo "python3 is required (https://www.python.org/downloads/)"; exit 1; }
python3 -m venv venv
./venv/bin/pip install --quiet --upgrade pip -r requirements.txt

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$P" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$L</string>
  <key>ProgramArguments</key><array><string>$DIR/venv/bin/python</string><string>$DIR/goose.py</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$DIR/goose.log</string>
  <key>StandardErrorPath</key><string>$DIR/goose.log</string>
</dict></plist>
PLIST

chmod +x goosectl
./goosectl stop >/dev/null 2>&1 || true
./goosectl start
echo "Goose installed. Control it with: $DIR/goosectl start|stop|restart|status|uninstall"
