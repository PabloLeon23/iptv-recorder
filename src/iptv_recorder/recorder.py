"""ffmpeg recording logic, conflict detection, and Plex file naming."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from zoneinfo import ZoneInfo

from .config import TMP_DIR, load_recordings, save_recordings
from .plex import refresh_library

MADRID = ZoneInfo("Europe/Madrid")
console = Console()


# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------

def find_ffmpeg() -> str:
    """Locate the ffmpeg binary or raise RuntimeError."""
    binary = shutil.which("ffmpeg")
    if binary:
        return binary

    if sys.platform == "win32":
        candidates = [
            Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
            Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
            Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
            Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
        for p in candidates:
            if p.exists():
                return str(p)

    raise RuntimeError(
        "ffmpeg not found. Install ffmpeg and add it to your PATH.\n"
        "Download: https://ffmpeg.org/download.html"
    )


def _build_cmd(
    ffmpeg_bin: str,
    stream_url: str,
    output_path: str,
    duration_seconds: int | None,
) -> list[str]:
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", stream_url,
    ]
    if duration_seconds is not None:
        cmd += ["-t", str(duration_seconds)]
    cmd += [
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    return cmd


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def cleanup_stale_recordings(recordings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark any 'recording' entry whose end time is past as 'failed'."""
    now = datetime.now(tz=timezone.utc)
    for rec in recordings:
        if rec.get("status") == "recording" and rec.get("end"):
            try:
                end = datetime.fromisoformat(rec["end"])
                if end < now:
                    rec["status"] = "failed"
            except ValueError:
                pass
    return recordings


def find_conflicts(
    new_start: datetime,
    new_end: datetime,
    recordings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return recordings that overlap with the [new_start, new_end) interval."""
    conflicts = []
    for rec in recordings:
        if rec.get("status") not in ("scheduled", "recording"):
            continue
        if not rec.get("end"):
            # Open-ended recording — always conflicts if it's active
            conflicts.append(rec)
            continue
        try:
            rec_start = datetime.fromisoformat(rec["start"])
            rec_end = datetime.fromisoformat(rec["end"])
        except (KeyError, ValueError):
            continue
        if new_start < rec_end and new_end > rec_start:
            conflicts.append(rec)
    return conflicts


# ---------------------------------------------------------------------------
# File naming
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Strip characters illegal on Windows/Linux filesystems."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = name.strip(". ")
    return name or "Unknown_Channel"


def build_plex_filename(channel_name: str, start: datetime, plex_folder: Path) -> str:
    """Return a Plex-compatible filename, disambiguating if the file already exists."""
    year = start.astimezone(MADRID).year
    safe = sanitize_filename(channel_name)
    base = f"{safe} ({year}).mp4"

    if not (plex_folder / base).exists():
        return base

    suffix = start.astimezone(MADRID).strftime("%Y%m%d-%H%M")
    return f"{safe} ({year}) [{suffix}].mp4"


# ---------------------------------------------------------------------------
# Main recording function
# ---------------------------------------------------------------------------

def run_recording(
    channel: dict[str, Any],
    start: datetime,
    end: datetime | None,
    config: dict[str, Any],
) -> None:
    """Execute a recording. Blocks until done or Ctrl+C."""

    ffmpeg_bin = find_ffmpeg()
    plex_cfg = config["plex"]
    plex_folder = Path(plex_cfg["movies_folder_path"])

    # --- Conflict check (only when end is known) ---
    recordings = cleanup_stale_recordings(load_recordings())
    if end is not None:
        conflicts = find_conflicts(start, end, recordings)
        if conflicts:
            console.print("\n[bold red]Conflict detected![/bold red] The following recordings overlap:")
            for c in conflicts:
                console.print(
                    f"  • [yellow]{c['channel_name']}[/yellow]  "
                    f"{c['start']} → {c.get('end', 'open-ended')}"
                )
            raise SystemExit(1)

    # --- Build paths ---
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    rec_id = str(uuid.uuid4())
    tmp_filename = f"rec_{rec_id}.mp4"
    tmp_path = TMP_DIR / tmp_filename

    duration_seconds: int | None = None
    if end is not None:
        now = datetime.now(tz=timezone.utc)
        effective_start = max(start.astimezone(timezone.utc), now)
        duration_seconds = max(1, int((end.astimezone(timezone.utc) - effective_start).total_seconds()))
        if duration_seconds <= 0:
            console.print("[red]End time is in the past. Nothing to record.[/red]")
            raise SystemExit(1)

    # --- Register recording ---
    entry: dict[str, Any] = {
        "id": rec_id,
        "channel_id": channel["id"],
        "channel_name": channel["name"],
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "status": "recording",
        "tmp_path": str(tmp_path),
    }
    recordings.append(entry)
    save_recordings(recordings)

    # --- Launch ffmpeg ---
    cmd = _build_cmd(ffmpeg_bin, channel["url"], str(tmp_path), duration_seconds)
    console.print(f"\n[bold green]Recording[/bold green] [cyan]{channel['name']}[/cyan]")
    if end:
        console.print(f"  Duration: {duration_seconds}s  →  [dim]{str(tmp_path)}[/dim]")
    else:
        console.print(f"  Press [bold]Ctrl+C[/bold] to stop  →  [dim]{str(tmp_path)}[/dim]")

    interrupted = False
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    start_time = time.monotonic()
    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                break
            elapsed = int(time.monotonic() - start_time)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            console.print(
                f"  [dim]Elapsed: {h:02d}:{m:02d}:{s:02d}[/dim]",
                end="\r",
                highlight=False,
            )
            time.sleep(1)
    except KeyboardInterrupt:
        interrupted = True
        console.print("\n[yellow]Stopping recording gracefully...[/yellow]")
        try:
            if proc.stdin:
                proc.stdin.write(b"q\n")
                proc.stdin.flush()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    console.print()

    # --- Update status ---
    recordings = load_recordings()
    for rec in recordings:
        if rec["id"] == rec_id:
            rec["status"] = "interrupted" if interrupted else (
                "done" if proc.returncode == 0 else "failed"
            )
            break
    save_recordings(recordings)

    # --- Post-processing ---
    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        console.print("[red]Recording produced no output. Nothing to copy to Plex.[/red]")
        return

    plex_filename = build_plex_filename(channel["name"], start, plex_folder)
    dest = plex_folder / plex_filename

    try:
        plex_folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp_path, dest)
        tmp_path.unlink(missing_ok=True)
        console.print(f"[green]Saved:[/green] {dest}")
    except OSError as exc:
        console.print(f"[red]Failed to copy to Plex folder:[/red] {exc}")
        return

    # --- Plex library refresh ---
    try:
        refresh_library(
            plex_cfg["server_url"],
            plex_cfg["movies_library_section_id"],
            plex_cfg["auth_token"],
        )
        console.print("[green]Plex library scan triggered.[/green]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Warning: could not trigger Plex scan:[/yellow] {exc}")
