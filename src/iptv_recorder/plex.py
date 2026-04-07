"""Plex Media Server API integration."""

from __future__ import annotations

from typing import Any

import httpx


def verify_plex_connection(server_url: str, token: str) -> bool:
    """Return True if the Plex server is reachable and the token is valid."""
    server_url = server_url.rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(server_url, params={"X-Plex-Token": token})
            return resp.status_code == 200
    except httpx.RequestError:
        return False


def list_library_sections(server_url: str, token: str) -> list[dict[str, Any]]:
    """Return all library sections with their ID, title, and type."""
    server_url = server_url.rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            f"{server_url}/library/sections",
            params={"X-Plex-Token": token},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()

    data = resp.json()
    sections = data.get("MediaContainer", {}).get("Directory", [])
    return [
        {"id": str(s.get("key", "")), "title": s.get("title", ""), "type": s.get("type", "")}
        for s in sections
    ]


def refresh_library(server_url: str, section_id: str, token: str) -> None:
    """Trigger an async library scan for the given section."""
    server_url = server_url.rstrip("/")
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{server_url}/library/sections/{section_id}/refresh",
            params={"X-Plex-Token": token},
        )
        resp.raise_for_status()
