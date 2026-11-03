#!/usr/bin/env bash
# =============================================================================
# TrackDown Telegram Bot — 24/7 Watchdog Supervisor & Auto-Healer Daemon
# =============================================================================

echo "=================================================================="
echo "🛡️ TrackDown Bot 24/7 Watchdog Supervisor Started"
echo "🕒 Initialized at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "⚙️ System: $(uname -s) $(uname -m) | Python: $(python3 --version 2>&1)"
echo "=================================================================="

RESTART_COUNT=0
MAX_RESTARTS=5000

while true; do
    echo "🚀 [$(date '+%H:%M:%S')] Launching telegram_bot.py..."
    python3 telegram_bot.py
    EXIT_CODE=$?
    
    echo "⚠️ [$(date '+%H:%M:%S')] Bot process exited with status code: ${EXIT_CODE}"
    RESTART_COUNT=$((RESTART_COUNT + 1))
    
    if [ $RESTART_COUNT -ge $MAX_RESTARTS ]; then
        echo "🚨 Critical: Reached maximum restart threshold (${MAX_RESTARTS}). Halting watchdog."
        exit 1
    fi
    
    echo "🔄 Auto-recovering in 2 seconds... (Restart #${RESTART_COUNT})"
    sleep 2
done
