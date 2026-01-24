"""Jarvis CLI - Command-line interface for the desktop agent."""

import typer

from jarvis import __version__

app = typer.Typer(
    name="jarvis",
    help="Jarvis Desktop Agent - Privacy-first screen capture for personal AI memory.",
    no_args_is_help=True,
)


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


@app.command()
def status() -> None:
    """Show agent status."""
    typer.echo("Agent status: not running")


if __name__ == "__main__":
    app()
