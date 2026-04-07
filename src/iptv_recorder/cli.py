"""iptv-recorder — CLI entry point."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import typer
from InquirerPy import inquirer
from rich.console import Console
from rich.table import Table
from zoneinfo import ZoneInfo

from .channels import pick_channel
from .config import (
    default_config,
    load_config,
    save_config,
)
from .playlist import get_channels, find_channel
from .plex import list_library_sections, verify_plex_connection
from .recorder import run_recording

app = typer.Typer(
    name="iptv-recorder",
    help="Record IPTV streams and deliver them to your Plex server.",
    add_completion=False,
)

console = Console()
MADRID = ZoneInfo("Europe/Madrid")


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

@app.command()
def setup() -> None:
    """Interactive first-time setup wizard."""

    console.print("\n[bold]IPTV Recorder — Setup[/bold]\n")

    config = default_config()

    # --- IPTV format ---
    fmt = inquirer.select(
        message="IPTV provider format:",
        choices=[
            {"name": "M3U playlist URL", "value": "m3u"},
            {"name": "Xtream Codes API (server + username + password)", "value": "xtream"},
        ],
    ).execute()
    config["iptv"]["format"] = fmt

    if fmt == "m3u":
        config["iptv"]["playlist_url"] = inquirer.text(
            message="M3U playlist URL:"
        ).execute().strip()

        use_auth = inquirer.confirm(
            message="Does this URL require HTTP basic auth?", default=False
        ).execute()
        if use_auth:
            config["iptv"]["xtream_username"] = inquirer.text(
                message="HTTP username:"
            ).execute().strip()
            config["iptv"]["xtream_password"] = inquirer.secret(
                message="HTTP password:"
            ).execute()
    else:
        config["iptv"]["xtream_server"] = inquirer.text(
            message="Xtream Codes server URL (e.g. http://provider.com:8080):"
        ).execute().strip()
        config["iptv"]["xtream_username"] = inquirer.text(
            message="Username:"
        ).execute().strip()
        config["iptv"]["xtream_password"] = inquirer.secret(
            message="Password:"
        ).execute()

    # --- Plex ---
    console.print("\n[bold]Plex configuration[/bold]")

    config["plex"]["server_url"] = inquirer.text(
        message="Plex server URL:",
        default="http://localhost:32400",
    ).execute().strip()

    config["plex"]["auth_token"] = inquirer.secret(
        message="Plex auth token (X-Plex-Token):"
    ).execute().strip()

    # Verify connection
    console.print("  Verifying Plex connection...", end=" ")
    if verify_plex_connection(config["plex"]["server_url"], config["plex"]["auth_token"]):
        console.print("[green]OK[/green]")
    else:
        console.print("[yellow]Could not connect — check URL and token (saving anyway)[/yellow]")

    # Library section
    section_id = _pick_library_section(config["plex"]["server_url"], config["plex"]["auth_token"])
    config["plex"]["movies_library_section_id"] = section_id

    config["plex"]["movies_folder_path"] = inquirer.text(
        message="Local path to your Plex Movies folder:"
    ).execute().strip()

    save_config(config)
    console.print(f"\n[green]Configuration saved.[/green]")


def _pick_library_section(server_url: str, token: str) -> str:
    try:
        sections = list_library_sections(server_url, token)
    except Exception:
        sections = []

    if sections:
        choices = [
            {"name": f"[{s['type']}] {s['title']}  (id={s['id']})", "value": s["id"]}
            for s in sections
        ]
        choices.append({"name": "Enter manually", "value": "__manual__"})
        section_id = inquirer.select(
            message="Plex Movies library section:",
            choices=choices,
        ).execute()
        if section_id != "__manual__":
            return section_id

    return inquirer.text(
        message="Plex Movies library section ID (numeric):"
    ).execute().strip()


# ---------------------------------------------------------------------------
# channels
# ---------------------------------------------------------------------------

@app.command()
def channels(
    refresh: Annotated[bool, typer.Option("--refresh", help="Re-fetch channel list from provider")] = False,
) -> None:
    """Browse and search channels interactively."""

    config = _require_config()

    with console.status("Loading channels..."):
        channel_list = get_channels(config, refresh=refresh)

    console.print(f"  [dim]{len(channel_list)} channels loaded[/dim]\n")

    selected = pick_channel(channel_list)
    if selected is None:
        raise typer.Exit()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[bold]Name[/bold]", selected["name"])
    table.add_row("[bold]Group[/bold]", selected.get("group", "—"))
    table.add_row("[bold]ID[/bold]", selected.get("id", "—"))
    table.add_row("[bold]URL[/bold]", selected["url"])
    console.print(table)


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

@app.command()
def record(
    channel: Annotated[str, typer.Option("--channel", "-c", help="Channel name or ID")] = "",
    start: Annotated[Optional[str], typer.Option("--start", "-s", help='Start time in Madrid TZ: "YYYY-MM-DD HH:MM"')] = None,
    end: Annotated[Optional[str], typer.Option("--end", "-e", help='End time in Madrid TZ: "YYYY-MM-DD HH:MM" (omit to record until Ctrl+C)')] = None,
) -> None:
    """Record an IPTV stream to your Plex library."""

    config = _require_config()

    # --- Resolve channel (interactive if not given) ---
    with console.status("Loading channels..."):
        channel_list = get_channels(config)

    if channel:
        ch = find_channel(channel_list, channel)
        if ch is None:
            console.print(f"[red]Channel not found:[/red] {channel}")
            console.print("Use [bold]iptv-recorder channels[/bold] to browse.")
            raise typer.Exit(1)
    else:
        console.print(f"  [dim]{len(channel_list)} channels loaded[/dim]\n")
        ch = pick_channel(channel_list)
        if ch is None:
            raise typer.Exit()

    # --- Parse times ---
    start_dt = _parse_madrid_datetime(start, "start") if start else datetime.now(tz=MADRID)
    end_dt = _parse_madrid_datetime(end, "end") if end else None

    if end_dt is not None and end_dt <= start_dt:
        console.print("[red]--end must be after --start.[/red]")
        raise typer.Exit(1)

    # --- Record ---
    run_recording(ch, start_dt, end_dt, config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_config() -> dict:
    try:
        return load_config()
    except typer.BadParameter as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


def _parse_madrid_datetime(value: str, label: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M"):
        try:
            naive = datetime.strptime(value.strip(), fmt)
            return naive.replace(tzinfo=MADRID)
        except ValueError:
            continue
    console.print(
        f'[red]Invalid {label} time:[/red] "{value}". '
        'Expected format: "YYYY-MM-DD HH:MM" (Madrid time)'
    )
    raise typer.Exit(1)
