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


def fetch_history(token: str) -> list[dict]:
    """Fetch listening history from Pocket Casts."""
    resp = requests.post(
        f"{API_BASE}/user/history",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"History response keys: {list(data.keys())}")
    episodes = data.get("episodes", [])
    print(f"Episodes returned: {len(episodes)}")
    if episodes:
        print(f"First episode keys: {list(episodes[0].keys())}")
        print(f"First episode: {json.dumps(episodes[0], indent=2, default=str)}")
    else:
        print(f"Full response: {json.dumps(data, indent=2, default=str)}")
    return episodes


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

    print("Fetching listening history...")
    episodes = fetch_history(token)

    print("Fetching podcast list...")
    podcasts = fetch_podcast_list(token)

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
            "url": ep.get("url", ""),
            "listened_date": now,
        })
        new_count += 1

    # Sort by listened date descending
    existing["episodes"].sort(key=lambda e: e["listened_date"], reverse=True)
    existing["last_synced"] = now

    save(existing)
    print(f"Sync complete. {new_count} new episode(s) added. Total: {len(existing['episodes'])}")


if __name__ == "__main__":
    sync()
