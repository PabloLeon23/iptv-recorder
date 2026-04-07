# CLAUDE.md — Developer Notes

## Project layout

```
src/iptv_recorder/
├── cli.py        # typer app — all CLI commands (setup, channels, record)
├── config.py     # load/save config.json and recordings.json
├── playlist.py   # fetch + parse M3U and Xtream Codes channel lists
├── channels.py   # InquirerPy fuzzy channel picker
├── recorder.py   # ffmpeg subprocess, conflict detection, file naming
└── plex.py       # Plex HTTP API calls (verify, refresh library)
```

## Development commands

```bash
uv sync                          # install dependencies
uv run iptv-recorder --help      # check CLI is wired up
uv run pytest                    # run tests
```

## Key design decisions

- **Both M3U and Xtream Codes** are normalised to the same channel dict schema: `{id, name, group, url}`.
- **InquirerPy** is used for all interactive prompts (cross-platform, no fzf binary required).
- Recordings use `ffmpeg -c copy` (stream remux, no re-encoding) into MP4 with `-movflags +faststart`.
- The file is written to a temp path during recording, then moved to the Plex folder on completion. This prevents Plex from scanning an incomplete file.
- **Ctrl+C** sends `q\n` to ffmpeg stdin for a graceful shutdown (finalizes the MP4 moov atom), then waits up to 10 s before force-killing.
- Conflict detection uses a simple interval overlap check on `~/.iptv-recorder/recordings.json`. Only `scheduled` and `recording` entries are considered. Stale `recording` entries past their end time are cleaned up automatically.
- `tzdata` is a hard dependency to support Windows (no system timezone database there).

## Windows compatibility

- Use `pathlib.Path` everywhere — never concatenate path strings.
- `subprocess.Popen` is called with a list, never `shell=True`.
- ffmpeg is located via `shutil.which` first, then falls back to common Windows paths.
