"""Configuration management CLI commands."""

import json
from pathlib import Path

import typer
import yaml

from jarvis.config import get_settings

config_app = typer.Typer(
    name="config",
    help="Configuration management - view and modify settings.",
    no_args_is_help=True,
)


def _output(data: dict, as_json: bool, human_lines: list[str]) -> None:
    """Output data as JSON or human-readable format."""
    if as_json:
        typer.echo(json.dumps(data))
    else:
        for line in human_lines:
            typer.echo(line)


@config_app.command()
def show(
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
    ),
) -> None:
    """Show current configuration."""
    settings = get_settings()

    config_data = {
        "capture_interval": settings.capture_interval,
        "idle_threshold": settings.idle_threshold,
        "jpeg_quality": settings.jpeg_quality,
        "server_url": settings.server_url,
        "exclusions_file": str(settings.exclusions_path),
        "data_dir": str(settings.data_path),
        "log_level": settings.log_level,
    }

    if output_json:
        typer.echo(json.dumps(config_data, indent=2))
    else:
        typer.echo("")
        typer.echo("Jarvis Configuration")
        typer.echo("--------------------")
        typer.echo(f"Capture interval: {settings.capture_interval}s")
        typer.echo(f"Idle threshold: {settings.idle_threshold}s")
        typer.echo(f"JPEG quality: {settings.jpeg_quality}")
        typer.echo(f"Server URL: {settings.server_url}")
        typer.echo(f"Exclusions file: {settings.exclusions_path}")
        typer.echo(f"Data directory: {settings.data_path}")
        typer.echo(f"Log level: {settings.log_level}")
        typer.echo("")
        typer.echo("Set values using environment variables with JARVIS_ prefix")
        typer.echo("Example: JARVIS_CAPTURE_INTERVAL=30")


@config_app.command(name="set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key to set"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value.

    Note: Configuration is primarily environment-based. This command
    helps you see what to set in your environment or .env file.
    """
    valid_keys = {
        "capture_interval",
        "idle_threshold",
        "jpeg_quality",
        "server_url",
        "log_level",
    }

    if key not in valid_keys:
        typer.echo(f"Unknown key: {key}")
        typer.echo(f"Valid keys: {', '.join(sorted(valid_keys))}")
        raise typer.Exit(1)

    env_key = f"JARVIS_{key.upper()}"
    typer.echo(f"To set {key}={value}, add to your environment:")
    typer.echo(f"  export {env_key}={value}")
    typer.echo("")
    typer.echo("Or add to ~/.config/jarvis/.env:")
    typer.echo(f"  {env_key}={value}")


# Exclusions subcommand group
exclusions_app = typer.Typer(
    name="exclusions",
    help="Manage capture exclusion rules.",
    no_args_is_help=True,
)
config_app.add_typer(exclusions_app, name="exclusions")


@exclusions_app.command(name="list")
def list_exclusions(
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format",
    ),
) -> None:
    """List current exclusion patterns."""
    settings = get_settings()
    exclusions = settings.load_exclusions()

    if output_json:
        typer.echo(json.dumps(exclusions, indent=2))
    else:
        typer.echo("")
        typer.echo("Capture Exclusions")
        typer.echo("------------------")
        typer.echo("")
        typer.echo("Excluded Applications:")
        for app in sorted(exclusions.get("app_names", [])):
            typer.echo(f"  - {app}")

        typer.echo("")
        typer.echo("Excluded Window Titles (patterns):")
        for title in sorted(exclusions.get("window_titles", [])):
            typer.echo(f"  - {title}")

        typer.echo("")
        typer.echo(f"File: {settings.exclusions_path}")


@exclusions_app.command()
def add(
    pattern: str = typer.Argument(..., help="Pattern to add"),
    title: bool = typer.Option(
        False,
        "--title",
        "-t",
        help="Add as window title pattern (default: app name)",
    ),
) -> None:
    """Add an exclusion pattern."""
    settings = get_settings()
    exclusions_path = settings.exclusions_path

    # Load existing user exclusions (not including defaults)
    if exclusions_path.exists():
        try:
            with open(exclusions_path) as f:
                exclusions = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            exclusions = {}
    else:
        exclusions = {}

    # Ensure lists exist
    exclusions.setdefault("app_names", [])
    exclusions.setdefault("window_titles", [])

    # Add pattern
    if title:
        if pattern.lower() not in [t.lower() for t in exclusions["window_titles"]]:
            exclusions["window_titles"].append(pattern.lower())
            typer.echo(f"Added window title pattern: {pattern}")
        else:
            typer.echo(f"Pattern already exists: {pattern}")
            return
    else:
        if pattern.lower() not in [a.lower() for a in exclusions["app_names"]]:
            exclusions["app_names"].append(pattern.lower())
            typer.echo(f"Added app name: {pattern}")
        else:
            typer.echo(f"App already excluded: {pattern}")
            return

    # Save
    exclusions_path.parent.mkdir(parents=True, exist_ok=True)
    with open(exclusions_path, "w") as f:
        yaml.dump(exclusions, f, default_flow_style=False)

    typer.echo(f"Saved to {exclusions_path}")


@exclusions_app.command()
def remove(
    pattern: str = typer.Argument(..., help="Pattern to remove"),
    title: bool = typer.Option(
        False,
        "--title",
        "-t",
        help="Remove from window titles (default: app names)",
    ),
) -> None:
    """Remove an exclusion pattern."""
    settings = get_settings()
    exclusions_path = settings.exclusions_path

    if not exclusions_path.exists():
        typer.echo("No user exclusions file found.")
        raise typer.Exit(1)

    try:
        with open(exclusions_path) as f:
            exclusions = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        typer.echo(f"Error reading exclusions: {e}")
        raise typer.Exit(1)

    # Remove pattern
    if title:
        patterns = exclusions.get("window_titles", [])
        pattern_lower = pattern.lower()
        matches = [p for p in patterns if p.lower() == pattern_lower]
        if matches:
            for m in matches:
                patterns.remove(m)
            typer.echo(f"Removed window title pattern: {pattern}")
        else:
            typer.echo(f"Pattern not found: {pattern}")
            return
    else:
        apps = exclusions.get("app_names", [])
        pattern_lower = pattern.lower()
        matches = [a for a in apps if a.lower() == pattern_lower]
        if matches:
            for m in matches:
                apps.remove(m)
            typer.echo(f"Removed app name: {pattern}")
        else:
            typer.echo(f"App not found: {pattern}")
            return

    # Save
    with open(exclusions_path, "w") as f:
        yaml.dump(exclusions, f, default_flow_style=False)

    typer.echo(f"Saved to {exclusions_path}")


@exclusions_app.command()
def wizard() -> None:
    """Interactive wizard to select applications to exclude.

    Lists running applications and lets you choose which ones
    to add to the exclusion list.
    """
    typer.echo("")
    typer.echo("Exclusion Wizard")
    typer.echo("----------------")
    typer.echo("")
    typer.echo("Scanning running applications...")

    # Get running windows
    try:
        import pywinctl
        windows = pywinctl.getAllWindows()
    except Exception as e:
        typer.echo(f"Error getting windows: {e}")
        typer.echo("Make sure you have display access.")
        raise typer.Exit(1)

    if not windows:
        typer.echo("No windows found.")
        raise typer.Exit(0)

    # Group by app name and count windows
    settings = get_settings()
    current_exclusions = settings.load_exclusions()
    excluded_apps = {a.lower() for a in current_exclusions.get("app_names", [])}

    apps: dict[str, dict] = {}
    for win in windows:
        try:
            app_name = win.getAppName()
            if not app_name:
                continue

            if app_name not in apps:
                apps[app_name] = {
                    "name": app_name,
                    "windows": 0,
                    "already_excluded": app_name.lower() in excluded_apps,
                }
            apps[app_name]["windows"] += 1
        except Exception:
            continue

    if not apps:
        typer.echo("No applications found.")
        raise typer.Exit(0)

    # Sort by name and display
    sorted_apps = sorted(apps.values(), key=lambda a: a["name"].lower())

    typer.echo("")
    typer.echo("Running Applications:")
    for i, app in enumerate(sorted_apps, 1):
        status = " [already excluded]" if app["already_excluded"] else ""
        window_count = app["windows"]
        window_str = f"{window_count} window{'s' if window_count != 1 else ''}"
        typer.echo(f"  {i:2}. {app['name']} ({window_str}){status}")

    typer.echo("")
    selection = typer.prompt(
        "Enter numbers to exclude (comma-separated), or 'q' to quit",
        default="q",
    )

    if selection.lower() == "q":
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    # Parse selection
    try:
        indices = [int(s.strip()) for s in selection.split(",") if s.strip()]
    except ValueError:
        typer.echo("Invalid input. Use comma-separated numbers.")
        raise typer.Exit(1)

    # Validate indices
    selected_apps = []
    for idx in indices:
        if 1 <= idx <= len(sorted_apps):
            app = sorted_apps[idx - 1]
            if not app["already_excluded"]:
                selected_apps.append(app["name"])
        else:
            typer.echo(f"Invalid number: {idx}")
            raise typer.Exit(1)

    if not selected_apps:
        typer.echo("No new apps selected.")
        raise typer.Exit(0)

    # Load existing user exclusions
    exclusions_path = settings.exclusions_path
    if exclusions_path.exists():
        try:
            with open(exclusions_path) as f:
                user_exclusions = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            user_exclusions = {}
    else:
        user_exclusions = {}

    user_exclusions.setdefault("app_names", [])
    user_exclusions.setdefault("window_titles", [])

    # Add selected apps
    added = []
    for app_name in selected_apps:
        if app_name.lower() not in [a.lower() for a in user_exclusions["app_names"]]:
            user_exclusions["app_names"].append(app_name.lower())
            added.append(app_name)

    # Save
    exclusions_path.parent.mkdir(parents=True, exist_ok=True)
    with open(exclusions_path, "w") as f:
        yaml.dump(user_exclusions, f, default_flow_style=False)

    typer.echo("")
    typer.echo("Added exclusions:")
    for app in added:
        typer.echo(f"  - {app}")

    typer.echo("")
    typer.echo(f"Exclusions saved to {exclusions_path}")
