#!/bin/bash
# Start the Memory Search HTTP server as a background daemon
# Usage: ./start-memory.sh [start|stop|status|restart]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.memory-server.pid"
LOG_FILE="$SCRIPT_DIR/.memory-server.log"

start_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Memory server already running (PID: $PID)"
            return 0
        fi
        rm "$PID_FILE"
    fi

    cd "$SCRIPT_DIR"

    # Activate venv if exists
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi

    echo "Starting Memory Search server..."
    nohup python server_http.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    # Wait a moment and check if started
    sleep 1
    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "Memory server started (PID: $(cat "$PID_FILE"))"
        echo "API: http://127.0.0.1:8765"
        echo "Health: http://127.0.0.1:8765/health"
    else
        echo "Failed to start server. Check $LOG_FILE"
        rm "$PID_FILE"
        return 1
    fi
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Stopping Memory server (PID: $PID)..."
            kill "$PID"
            rm "$PID_FILE"
            echo "Stopped."
        else
            echo "Server not running (stale PID file)"
            rm "$PID_FILE"
        fi
    else
        echo "No PID file found. Server not running."
    fi
}

status_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Memory server running (PID: $PID)"
            # Quick health check
            if curl -s http://127.0.0.1:8765/health > /dev/null 2>&1; then
                echo "Health: OK"
            else
                echo "Health: Not responding"
            fi
        else
            echo "Server not running (stale PID file)"
        fi
    else
        echo "Server not running"
    fi
}

case "${1:-start}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    status)
        status_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac
