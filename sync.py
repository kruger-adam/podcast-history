#!/usr/bin/env python3
"""Sync Pocket Casts listening history to a local JSON file."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE = "https://api.pocketcasts.com"
DATA_FILE = Path(__file__).parent / "data" / "history.json"


def login(email: str, password: str) -> str:
    """Authenticate and return a bearer token."""
    resp = requests.post(
        f"{API_BASE}/user/login",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        print("Login failed: no token in response", file=sys.stderr)
        sys.exit(1)
    return token


def fetch_episodes(token: str) -> list[dict]:
    """Fetch episodes from both history and in-progress endpoints."""
    all_episodes = {}

    for endpoint in ["/user/history", "/user/in_progress"]:
        resp = requests.post(
            f"{API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        resp.raise_for_status()
        episodes = resp.json().get("episodes", [])
        print(f"  {endpoint}: {len(episodes)} episode(s)")
        for ep in episodes:
            uuid = ep.get("uuid")
            if uuid:
                all_episodes[uuid] = ep

    print(f"Total unique episodes: {len(all_episodes)}")
    return list(all_episodes.values())


def fetch_podcast_list(token: str) -> dict[str, str]:
    """Fetch subscribed podcasts and return a uuid -> title mapping."""
    resp = requests.post(
        f"{API_BASE}/user/podcast/list",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    resp.raise_for_status()
    podcasts = resp.json().get("podcasts", [])
    return {p["uuid"]: p.get("title", "Unknown Podcast") for p in podcasts}


def fetch_stats(token: str) -> dict:
    """Fetch user listening stats."""
    resp = requests.post(
        f"{API_BASE}/user/stats/summary",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    resp.raise_for_status()
    return resp.json()


def load_existing() -> dict:
    """Load the existing history file, or return an empty structure."""
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"episodes": [], "last_synced": None}


def save(data: dict) -> None:
    """Write the history data to disk."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def sync():
    email = os.environ.get("POCKETCASTS_EMAIL")
    password = os.environ.get("POCKETCASTS_PASSWORD")
    if not email or not password:
        print("Set POCKETCASTS_EMAIL and POCKETCASTS_PASSWORD env vars", file=sys.stderr)
        sys.exit(1)

    print("Logging in...")
    token = login(email, password)

    print("Fetching episodes...")
    episodes = fetch_episodes(token)

    print("Fetching podcast list...")
    podcasts = fetch_podcast_list(token)

    print("Fetching user stats...")
    stats = fetch_stats(token)

    existing = load_existing()
    known_uuids = {ep["uuid"] for ep in existing["episodes"]}

    now = datetime.now(timezone.utc).isoformat()
    new_count = 0

    for ep in episodes:
        if ep.get("uuid") in known_uuids:
            continue

        existing["episodes"].append({
            "uuid": ep.get("uuid"),
            "title": ep.get("title", "Untitled"),
            "podcast_uuid": ep.get("podcastUuid", ""),
            "podcast_title": podcasts.get(ep.get("podcastUuid", ""), ep.get("podcastTitle", "Unknown Podcast")),
            "published_at": ep.get("published", ""),
            "duration": ep.get("duration", 0),
            "played_up_to": ep.get("playedUpTo", 0),
            "url": ep.get("url", ""),
            "listened_date": now,
        })
        new_count += 1

    # Sort by listened date descending
    existing["episodes"].sort(key=lambda e: e["listened_date"], reverse=True)
    existing["last_synced"] = now
    existing["stats"] = stats

    save(existing)
    print(f"Sync complete. {new_count} new episode(s) added. Total: {len(existing['episodes'])}")


if __name__ == "__main__":
    sync()
