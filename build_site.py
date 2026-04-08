#!/usr/bin/env python3
"""Build a static HTML page from the listening history JSON."""

import json
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "history.json"
OUTPUT_DIR = Path(__file__).parent / "site"
TEMPLATE = Path(__file__).parent / "template.html"


def build():
    if not DATA_FILE.exists():
        print("No history data found. Run sync.py first.")
        return

    with open(DATA_FILE) as f:
        data = json.load(f)

    with open(TEMPLATE) as f:
        html_template = f.read()

    episodes = data["episodes"]
    last_synced = data.get("last_synced", "")

    # Group episodes by month
    months: dict[str, list[dict]] = {}
    for ep in episodes:
        dt = datetime.fromisoformat(ep["listened_date"])
        key = dt.strftime("%B %Y")
        months.setdefault(key, []).append(ep)

    # Build episode HTML
    episodes_html = ""
    for month, eps in months.items():
        episodes_html += f'<h2 class="month-header">{month}</h2>\n'
        for ep in eps:
            published = ""
            if ep.get("published_at"):
                try:
                    pub_dt = datetime.fromisoformat(ep["published_at"].replace("Z", "+00:00"))
                    published = pub_dt.strftime("%b %d, %Y")
                except (ValueError, AttributeError):
                    published = ep["published_at"]

            duration_min = ep.get("duration", 0) // 60
            duration_str = f"{duration_min} min" if duration_min else ""

            episodes_html += f"""<div class="episode">
  <div class="episode-podcast">{escape(ep.get('podcast_title', ''))}</div>
  <div class="episode-title">{escape(ep.get('title', ''))}</div>
  <div class="episode-meta">
    {f'<span>{published}</span>' if published else ''}
    {f'<span>{duration_str}</span>' if duration_str else ''}
  </div>
</div>
"""

    # Stats
    podcast_set = {ep.get("podcast_title") for ep in episodes}
    total_minutes = sum(ep.get("duration", 0) for ep in episodes) // 60
    stats_html = f"""
    <div class="stats">
      <div class="stat"><span class="stat-num">{len(episodes)}</span> episodes</div>
      <div class="stat"><span class="stat-num">{len(podcast_set)}</span> podcasts</div>
      <div class="stat"><span class="stat-num">{total_minutes:,}</span> minutes</div>
    </div>
    """

    synced_str = ""
    if last_synced:
        try:
            synced_dt = datetime.fromisoformat(last_synced)
            synced_str = synced_dt.strftime("%B %d, %Y at %I:%M %p UTC")
        except (ValueError, AttributeError):
            synced_str = last_synced

    html = html_template.replace("{{EPISODES}}", episodes_html)
    html = html.replace("{{STATS}}", stats_html)
    html = html.replace("{{LAST_SYNCED}}", synced_str)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "index.html", "w") as f:
        f.write(html)

    print(f"Site built: {OUTPUT_DIR / 'index.html'}")


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


if __name__ == "__main__":
    build()
