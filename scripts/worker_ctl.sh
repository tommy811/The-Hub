#!/usr/bin/env bash
# scripts/worker_ctl.sh — Manage the discovery worker as a macOS launchd user agent.
#
# Why launchd: The Hub's discovery worker (scripts/worker.py) needs to be
# always-on so a "Re-run Discovery" click is picked up within seconds. PROJECT_STATE
# §15 deliberately avoids in-app runtime agents at production scale; for the
# single-machine dev box, launchd is the standard macOS pattern.
#
# Usage:
#   scripts/worker_ctl.sh install     # one-time: write plist, load it, start worker
#   scripts/worker_ctl.sh start       # start (no-op if already running)
#   scripts/worker_ctl.sh stop        # send SIGTERM (KeepAlive will restart it)
#   scripts/worker_ctl.sh unload      # disable auto-restart (until next install or load)
#   scripts/worker_ctl.sh status      # show launchd status row + last 5 log lines
#   scripts/worker_ctl.sh log         # tail -f the stdout log
#   scripts/worker_ctl.sh err         # tail -f the stderr log
#   scripts/worker_ctl.sh uninstall   # unload + delete plist

set -euo pipefail

LABEL="com.thehub.worker"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/the-hub-worker.log"
ERR_FILE="$LOG_DIR/the-hub-worker.err.log"
PYTHON_BIN="$(command -v python3 || true)"
WORKER_SCRIPT="$REPO_ROOT/scripts/worker.py"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "ERROR: python3 not found on PATH" >&2
  exit 1
fi

write_plist() {
  mkdir -p "$(dirname "$PLIST_DEST")" "$LOG_DIR"
  cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${WORKER_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${REPO_ROOT}/scripts</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>${LOG_FILE}</string>
  <key>StandardErrorPath</key>
  <string>${ERR_FILE}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
EOF
  echo "Wrote $PLIST_DEST"
}

case "${1:-help}" in
  install)
    write_plist
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    launchctl load "$PLIST_DEST"
    echo "Loaded ${LABEL}. Worker is now managed by launchd."
    echo "  stdout: $LOG_FILE"
    echo "  stderr: $ERR_FILE"
    ;;
  start)
    launchctl start "$LABEL"
    echo "Started ${LABEL}"
    ;;
  stop)
    launchctl stop "$LABEL"
    echo "Stopped ${LABEL} (KeepAlive will restart it; use 'unload' to disable auto-restart)"
    ;;
  restart)
    # Picks up code changes to scripts/worker.py + pipeline. KeepAlive auto-respawns.
    launchctl stop "$LABEL"
    echo "Restart triggered (launchd will respawn within ThrottleInterval=10s with fresh code)"
    ;;
  unload)
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    echo "Unloaded ${LABEL} (no auto-restart until next install/load)"
    ;;
  status)
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "launchd job: gui/$(id -u)/$LABEL"
      launchctl print "gui/$(id -u)/$LABEL" | grep -E "state =|pid =|runs ="
      echo
      echo "--- last 5 stdout lines ---"
      tail -n 5 "$LOG_FILE" 2>/dev/null || echo "(no stdout yet)"
    else
      echo "Not loaded. Run: scripts/worker_ctl.sh install"
    fi
    ;;
  log)
    echo "Tailing $LOG_FILE (Ctrl+C to stop)"
    tail -f "$LOG_FILE"
    ;;
  err)
    echo "Tailing $ERR_FILE (Ctrl+C to stop)"
    tail -f "$ERR_FILE"
    ;;
  uninstall)
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    echo "Removed $PLIST_DEST"
    ;;
  *)
    echo "Usage: $0 {install|start|stop|restart|unload|status|log|err|uninstall}"
    exit 1
    ;;
esac
