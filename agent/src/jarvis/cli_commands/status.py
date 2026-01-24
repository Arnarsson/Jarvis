"""Status command for Jarvis CLI."""

import json
import os
from datetime import datetime
from pathlib import Path

import typer

# PID and state file locations (shared with capture.py)
PID_FILE = Path("~/.local/share/jarvis/agent.pid").expanduser()
PAUSE_FILE = Path("~/.local/share/jarvis/agent.paused").expanduser()
QUEUE_DB = Path("~/.local/share/jarvis/upload_queue.db").expanduser()


def _get_running_pid() -> int | None:
    """Get the PID of the running agent, if any."""
    if not PID_FILE.exists():
        return None

    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process exists
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        # Invalid PID or process doesn't exist
        return None


def _get_queue_stats() -> dict:
    """Get upload queue statistics."""
    if not QUEUE_DB.exists():
        return {"pending": 0, "uploading": 0, "failed": 0, "total": 0}

    try:
        from jarvis.sync.queue import UploadQueue
        queue = UploadQueue(QUEUE_DB)
        stats = queue.get_stats()
        queue.close()
        return stats
    except Exception:
        return {"pending": 0, "uploading": 0, "failed": 0, "total": 0}


def _format_time_ago(timestamp: datetime | None) -> str:
    """Format a timestamp as 'X minutes ago' style string."""
    if timestamp is None:
        return "Never"

    now = datetime.utcnow()
    diff = now - timestamp

    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def status_command(
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
    ),
) -> None:
    """Show agent status.

    Displays whether the agent is running, its current state,
    and capture statistics.
    """
    pid = _get_running_pid()
    is_running = pid is not None
    is_paused = PAUSE_FILE.exists() and is_running

    if is_running:
        state = "paused" if is_paused else "active"
    else:
        state = "stopped"

    queue_stats = _get_queue_stats()

    # Build status data
    status_data = {
        "running": is_running,
        "state": state,
        "pid": pid,
        "queue_pending": queue_stats.get("pending", 0),
        "queue_failed": queue_stats.get("failed", 0),
    }

    if output_json:
        typer.echo(json.dumps(status_data))
    else:
        typer.echo("")
        typer.echo("Jarvis Agent Status")
        typer.echo("-------------------")

        if is_running:
            state_display = "Active (capturing)" if not is_paused else "Paused"
            typer.echo(f"State: {state_display}")
            typer.echo(f"PID: {pid}")
        else:
            typer.echo("State: Not running")

        typer.echo(f"Queue: {queue_stats.get('pending', 0)} pending uploads")
        if queue_stats.get("failed", 0) > 0:
            typer.echo(f"Failed: {queue_stats.get('failed', 0)} uploads")
        typer.echo("")

        if not is_running:
            typer.echo("Start the agent with: jarvis capture start")
