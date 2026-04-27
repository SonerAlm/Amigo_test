#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_LABEL="com.amigo.performancereport"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
PYTHON="$(which python3)"
TMP_DIR="$SCRIPT_DIR/.tmp"
LOG_OUT="$TMP_DIR/launchd_stdout.log"
LOG_ERR="$TMP_DIR/launchd_stderr.log"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$TMP_DIR"

echo "Creating launchd plist at $PLIST_PATH..."

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${SCRIPT_DIR}/run_report.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${SCRIPT_DIR}</string>

  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>5</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>5</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>5</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>5</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>5</integer><key>Minute</key><integer>0</integer></dict>
  </array>

  <key>StandardOutPath</key>
  <string>${LOG_OUT}</string>

  <key>StandardErrorPath</key>
  <string>${LOG_ERR}</string>

  <key>RunAtLoad</key>
  <false/>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    <key>HOME</key>
    <string>${HOME}</string>
  </dict>
</dict>
</plist>
EOF

# Unload existing (suppress error if not loaded)
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load the new plist
launchctl load -w "$PLIST_PATH"

echo ""
echo "Scheduled: Mon-Fri 5:00am (Mac local time) → $SCRIPT_DIR/run_report.py"
echo ""
echo "Useful commands:"
echo "  Test now:     launchctl start $PLIST_LABEL"
echo "  Check status: launchctl list | grep amigo"
echo "  View logs:    tail -f $LOG_ERR"
echo "  Unload:       launchctl unload $PLIST_PATH"
