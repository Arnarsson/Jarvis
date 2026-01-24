"""Capture management CLI commands."""

import json
import os
import signal
import sys
from pathlib import Path

import typer

from jarvis.config import get_settings

capture_app = typer.Typer(
    name="capture",
    help="Capture management - start, stop, pause, resume the agent.",
    no_args_is_help=True,
)

# PID file location for process management
PID_FILE = Path("~/.local/share/jarvis/agent.pid").expanduser()
PAUSE_FILE = Path("~/.local/share/jarvis/agent.paused").expanduser()


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
        PID_FILE.unlink(missing_ok=True)
        return None


def _write_pid() -> None:
    """Write current process PID to file."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _cleanup_pid() -> None:
    """Remove PID file on exit."""
    PID_FILE.unlink(missing_ok=True)
    PAUSE_FILE.unlink(missing_ok=True)


def _output(data: dict, as_json: bool, human_message: str) -> None:
    """Output data as JSON or human-readable format."""
    if as_json:
        typer.echo(json.dumps(data))
    else:
        typer.echo(human_message)


@capture_app.command()
def start(
    interval: int = typer.Option(
        None,
        "--interval",
        "-i",
        help="Capture interval in seconds (default: from config)",
    ),
    no_tray: bool = typer.Option(
        False,
        "--no-tray",
        help="Disable system tray icon",
    ),
    background: bool = typer.Option(
        False,
        "--background",
        "-b",
        help="Run in background (daemonize)",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
    ),
) -> None:
    """Start the capture agent.

    Launches the Jarvis capture agent which takes screenshots at regular
    intervals and uploads them to the server. Press Ctrl+C to stop.
    """
    # Check if already running
    existing_pid = _get_running_pid()
    if existing_pid:
        _output(
            {"status": "error", "message": "Agent already running", "pid": existing_pid},
            output_json,
            f"Agent already running (PID: {existing_pid}). Use 'jarvis capture stop' first.",
        )
        raise typer.Exit(1)

    settings = get_settings()
    capture_interval = interval or settings.capture_interval

    if background:
        # Daemonize: fork and exit parent
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process - exit
                _output(
                    {"status": "started", "pid": pid, "background": True},
                    output_json,
                    f"Starting Jarvis capture agent in background (PID: {pid})...",
                )
                raise typer.Exit(0)
        except OSError as e:
            _output(
                {"status": "error", "message": str(e)},
                output_json,
                f"Failed to daemonize: {e}",
            )
            raise typer.Exit(1)

        # Child process continues
        os.setsid()
        # Redirect stdout/stderr to /dev/null in daemon mode
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
    else:
        _output(
            {"status": "starting", "pid": os.getpid()},
            output_json,
            f"Starting Jarvis capture agent (interval: {capture_interval}s)...",
        )

    # Write PID file
    _write_pid()

    # Set up signal handlers for graceful shutdown
    def handle_signal(signum: int, frame) -> None:
        if not background:
            typer.echo("\nStopping Jarvis agent...")
        _cleanup_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        import asyncio
        from jarvis.engine.orchestrator import CaptureOrchestrator

        if not background:
            typer.echo("Agent started. Press Ctrl+C to stop.")

        # Override capture interval if provided
        if interval:
            settings.capture_interval = capture_interval

        orchestrator = CaptureOrchestrator(settings)

        async def run_orchestrator():
            try:
                await orchestrator.start()
            except asyncio.CancelledError:
                pass
            finally:
                await orchestrator.stop()

        asyncio.run(run_orchestrator())

    except KeyboardInterrupt:
        pass
    finally:
        _cleanup_pid()


@capture_app.command()
def stop(
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
    ),
) -> None:
    """Stop the running capture agent."""
    pid = _get_running_pid()

    if not pid:
        _output(
            {"status": "not_running"},
            output_json,
            "No agent is currently running.",
        )
        return

    try:
        os.kill(pid, signal.SIGTERM)
        _output(
            {"status": "stopped", "pid": pid},
            output_json,
            f"Stopping Jarvis agent (PID: {pid})...",
        )
    except OSError as e:
        _output(
            {"status": "error", "message": str(e)},
            output_json,
            f"Failed to stop agent: {e}",
        )
        raise typer.Exit(1)


@capture_app.command()
def pause(
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
    ),
) -> None:
    """Pause capture (agent keeps running but stops capturing)."""
    pid = _get_running_pid()

    if not pid:
        _output(
            {"status": "not_running"},
            output_json,
            "No agent is currently running.",
        )
        raise typer.Exit(1)

    # Create pause signal file
    PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAUSE_FILE.touch()

    _output(
        {"status": "paused", "pid": pid},
        output_json,
        "Capture paused. Use 'jarvis capture resume' to continue.",
    )


@capture_app.command()
def resume(
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
    ),
) -> None:
    """Resume capture after pause."""
    pid = _get_running_pid()

    if not pid:
        _output(
            {"status": "not_running"},
            output_json,
            "No agent is currently running.",
        )
        raise typer.Exit(1)

    if not PAUSE_FILE.exists():
        _output(
            {"status": "not_paused"},
            output_json,
            "Agent is not paused.",
        )
        return

    # Remove pause signal file
    PAUSE_FILE.unlink(missing_ok=True)

    _output(
        {"status": "resumed", "pid": pid},
        output_json,
        "Capture resumed.",
    )
