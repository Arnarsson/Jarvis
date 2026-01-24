"""CLI command modules for Jarvis desktop agent."""

from jarvis.cli_commands.capture import capture_app
from jarvis.cli_commands.status import status_command

__all__ = ["capture_app", "status_command"]
