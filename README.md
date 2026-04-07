# iptv-recorder

CLI tool to record IPTV live streams and deliver them to a local Plex server.

## Features

- Supports **M3U** and **Xtream Codes** IPTV providers
- Fuzzy interactive channel search — type to filter thousands of channels instantly
- Records with **ffmpeg** — fast stream copy (no re-encoding), MP4 output
- Detects scheduling conflicts before recording starts
- Copies recordings to a Plex **Movies** library folder and triggers a Plex library scan
- Open-ended recording (no `--end`) runs until you press **Ctrl+C** — the file is finalized gracefully

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- [ffmpeg](https://ffmpeg.org/) on your PATH (or installed in a common location)
- A running local Plex Media Server

## Installation

```bash
git clone <repo-url>
cd iptv-recorder
uv sync
```

## First-time setup

```bash
uv run iptv-recorder setup
```

This wizard asks for your IPTV provider details and Plex configuration, then saves them to `~/.iptv-recorder/config.json`.

You will need:
- Your IPTV playlist URL (M3U) or Xtream Codes server URL + credentials
- Your Plex server URL (default: `http://localhost:32400`)
- Your Plex auth token — find it at: Plex Web → Account → Authorized Devices → click any device → XML → `X-Plex-Token`
- The Plex library section ID for your Movies library (shown during setup)
- The local filesystem path to your Plex Movies folder

## Usage

### Browse / search channels

```bash
uv run iptv-recorder channels
```

Start typing to filter. Use arrow keys to navigate, Enter to select.

Refresh the channel cache from the provider:

```bash
uv run iptv-recorder channels --refresh
```

### Record a stream

With a fixed end time:

```bash
uv run iptv-recorder record --channel "Canal 24H" --start "2026-04-07 20:00" --end "2026-04-07 22:00"
```

Record until you press Ctrl+C:

```bash
uv run iptv-recorder record --channel "BBC World News" --start "2026-04-07 21:00"
```

Datetimes are in **Madrid time** (Europe/Madrid). If `--start` is in the past, recording begins immediately and runs until `--end` (or Ctrl+C).

## Windows notes

- Install ffmpeg and add its `bin/` folder to your PATH, or place it at `C:\ffmpeg\bin\ffmpeg.exe`.
- Run commands in **Windows Terminal** (not MSYS2 mintty or old `cmd.exe`) for the best interactive experience.
- All paths use Python's `pathlib` so they work correctly on both Windows and Linux.

## Config file location

`~/.iptv-recorder/config.json`

Channel cache: `~/.iptv-recorder/channels_cache.json`

Recording history: `~/.iptv-recorder/recordings.json`
