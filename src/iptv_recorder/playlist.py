"""Fetch and parse IPTV channel lists — supports M3U and Xtream Codes."""

from __future__ import annotations

import re
from typing import Any

import httpx

from .config import load_channel_cache, save_channel_cache

# ---------------------------------------------------------------------------
# Shared channel schema: {"id": str, "name": str, "group": str, "url": str}
# ---------------------------------------------------------------------------

_EXTINF_RE = re.compile(
    r"#EXTINF\s*:\s*-?\d+(?P<attrs>[^,]*),\s*(?P<name>.+)",
    re.IGNORECASE,
)
_ATTR_RE = re.compile(r'([\w-]+)=["\']([^"\']*)["\']')


def _parse_extinf(line: str) -> tuple[str, str, str]:
    """Return (tvg_id, group_title, display_name) from an #EXTINF line."""
    m = _EXTINF_RE.match(line)
    if not m:
        return "", "", line.strip()

    attrs_str = m.group("attrs")
    name = m.group("name").strip()

    attrs: dict[str, str] = {}
    for key, value in _ATTR_RE.findall(attrs_str):
        attrs[key.lower()] = value

    tvg_id = attrs.get("tvg-id", "")
    group = attrs.get("group-title", "")
    # Prefer tvg-name if present, otherwise use the trailing name
    display = attrs.get("tvg-name", "") or name
    return tvg_id, group, display


def fetch_m3u(url: str, username: str = "", password: str = "") -> list[dict[str, Any]]:
    """Download and parse an M3U playlist, returning a normalised channel list."""
    auth = (username, password) if username else None
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(url, auth=auth)
        resp.raise_for_status()

    try:
        text = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        text = resp.content.decode("latin-1")

    channels: list[dict[str, Any]] = []
    pending: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.upper().startswith("#EXTINF"):
            tvg_id, group, name = _parse_extinf(line)
            pending = {"id": tvg_id, "name": name, "group": group}
        elif line.startswith("#"):
            continue
        else:
            if pending is not None:
                pending["url"] = line
                channels.append(pending)
                pending = None

    return channels


def fetch_xtream(server: str, username: str, password: str) -> list[dict[str, Any]]:
    """Fetch live streams from an Xtream Codes API."""
    server = server.rstrip("/")
    base_params = {"username": username, "password": password}

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        # Fetch categories for group name lookup
        cat_resp = client.get(
            f"{server}/player_api.php",
            params={**base_params, "action": "get_live_categories"},
        )
        cat_resp.raise_for_status()
        categories: dict[str, str] = {
            str(c.get("category_id", "")): c.get("category_name", "")
            for c in cat_resp.json()
        }

        # Fetch streams
        streams_resp = client.get(
            f"{server}/player_api.php",
            params={**base_params, "action": "get_live_streams"},
        )
        streams_resp.raise_for_status()
        streams = streams_resp.json()

    channels: list[dict[str, Any]] = []
    for stream in streams:
        stream_id = str(stream.get("stream_id", ""))
        name = stream.get("name", "").strip()
        cat_id = str(stream.get("category_id", ""))
        group = categories.get(cat_id, "")
        url = f"{server}/live/{username}/{password}/{stream_id}.m3u8"
        channels.append({"id": stream_id, "name": name, "group": group, "url": url})

    return channels


def get_channels(config: dict[str, Any], refresh: bool = False) -> list[dict[str, Any]]:
    """Return channels from cache (or fetch from provider if missing/refresh)."""
    if not refresh:
        cached = load_channel_cache()
        if cached is not None:
            return cached

    iptv = config["iptv"]
    fmt = iptv.get("format", "m3u")

    if fmt == "xtream":
        channels = fetch_xtream(
            iptv["xtream_server"],
            iptv["xtream_username"],
            iptv["xtream_password"],
        )
    else:
        channels = fetch_m3u(
            iptv["playlist_url"],
            iptv.get("xtream_username", ""),
            iptv.get("xtream_password", ""),
        )

    save_channel_cache(channels)
    return channels


def find_channel(channels: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Find a channel by exact name (case-insensitive) or by stream ID."""
    name_lower = name.lower()
    for ch in channels:
        if ch["name"].lower() == name_lower or ch["id"] == name:
            return ch
    # Partial match fallback
    for ch in channels:
        if name_lower in ch["name"].lower():
            return ch
    return None
