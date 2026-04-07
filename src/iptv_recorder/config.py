"""Configuration management — load/save config.json and recordings.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

CONFIG_DIR = Path.home() / ".iptv-recorder"
CONFIG_FILE = CONFIG_DIR / "config.json"
RECORDINGS_FILE = CONFIG_DIR / "recordings.json"
CACHE_FILE = CONFIG_DIR / "channels_cache.json"
TMP_DIR = CONFIG_DIR / "tmp"

_EMPTY_CONFIG: dict[str, Any] = {
    "iptv": {
        "format": "",
        "playlist_url": "",
        "xtream_server": "",
        "xtream_username": "",
        "xtream_password": "",
    },
    "plex": {
        "server_url": "http://localhost:32400",
        "auth_token": "",
        "movies_library_section_id": "",
        "movies_folder_path": "",
    },
}


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise typer.BadParameter(
            "No configuration found. Run [bold]iptv-recorder setup[/bold] first.",
            param_hint="config",
        )
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any]) -> None:
    ensure_dirs()
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def default_config() -> dict[str, Any]:
    import copy
    return copy.deepcopy(_EMPTY_CONFIG)


def load_recordings() -> list[dict[str, Any]]:
    if not RECORDINGS_FILE.exists():
        return []
    try:
        return json.loads(RECORDINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_recordings(recordings: list[dict[str, Any]]) -> None:
    ensure_dirs()
    RECORDINGS_FILE.write_text(
        json.dumps(recordings, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_channel_cache() -> list[dict[str, Any]] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_channel_cache(channels: list[dict[str, Any]]) -> None:
    ensure_dirs()
    CACHE_FILE.write_text(
        json.dumps(channels, indent=2, ensure_ascii=False), encoding="utf-8"
    )
