"""Jarvis CLI - Command-line interface for the desktop agent."""

import typer

from jarvis import __version__
from jarvis.cli_commands.capture import capture_app
from jarvis.cli_commands.status import status_command

app = typer.Typer(
    name="jarvis",
    help="Jarvis Desktop Agent - Privacy-first screen capture for personal AI memory.",
    no_args_is_help=True,
)

# Register subcommands
app.add_typer(capture_app, name="capture")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"jarvis-agent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Jarvis Desktop Agent - Privacy-first screen capture."""
    pass


# Register status as a direct command on the main app
app.command(name="status")(status_command)


if __name__ == "__main__":
    app()
