#!/usr/bin/env bash
# Jarvis Agent Health Check Script
# Checks if captures are happening and restarts if stuck

set -euo pipefail

LOG_FILE="$HOME/.local/share/jarvis/health-check.log"
CAPTURE_DIR="$HOME/.local/share/jarvis/captures"
MIN_CAPTURES=1  # Expect at least 1 capture per check interval

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Check if service is running
if ! systemctl --user is-active jarvis-agent.service >/dev/null 2>&1; then
    log "ERROR: jarvis-agent.service is not active. Starting..."
    systemctl --user start jarvis-agent.service
    exit 1
fi

# Check if captures directory exists
if [[ ! -d "$CAPTURE_DIR" ]]; then
    log "WARNING: Capture directory does not exist: $CAPTURE_DIR"
    exit 0
fi

# Count recent captures (last 30 minutes)
RECENT_CAPTURES=$(find "$CAPTURE_DIR" -type f -mmin -30 -name "*.png" 2>/dev/null | wc -l)

log "Health check: $RECENT_CAPTURES captures in last 30 minutes"

# If no captures, restart the service
if [[ "$RECENT_CAPTURES" -lt "$MIN_CAPTURES" ]]; then
    log "WARNING: Only $RECENT_CAPTURES captures in last 30min (expected >=$MIN_CAPTURES). Restarting service..."
    systemctl --user restart jarvis-agent.service
    log "Service restarted"
    exit 1
fi

log "Health check passed"
exit 0
