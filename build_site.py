#!/usr/bin/env python3
"""Build a static HTML page from the listening history JSON."""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

DATA_FILE = Path(__file__).parent / "data" / "history.json"
NOTES_FILE = Path(__file__).parent / "data" / "notes.json"
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

    notes = {}
    if NOTES_FILE.exists():
        with open(NOTES_FILE) as f:
            notes = json.load(f)

    episodes = data["episodes"]
    last_synced = data.get("last_synced", "")

    # Group episodes by month
    months: dict[str, list[dict]] = {}
    episodes = [ep for ep in episodes if (ep.get("played_up_to", 0) or ep.get("duration", 0)) >= 60]

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

            duration = ep.get("duration", 0)
            played = ep.get("played_up_to", 0) or duration
            duration_min = duration // 60
            played_min = played // 60
            if duration_min and played_min < duration_min - 1:
                duration_str = f"{played_min}/{duration_min} min"
            elif duration_min:
                duration_str = f"✓ {duration_min} min"
            else:
                duration_str = ""

            artwork_url = f"https://static.pocketcasts.com/discover/images/webp/200/{ep.get('podcast_uuid', '')}.webp"

            ep_notes = notes.get(ep.get("uuid", ""), {})
            notes_html = ""
            note_parts = ""
            if ep_notes.get("reason"):
                note_parts += f'<div class="episode-note"><span class="note-label">Why I listened:</span> {escape(ep_notes["reason"])}</div>'
            if ep_notes.get("takeaways"):
                note_parts += f'<div class="episode-note"><span class="note-label">Takeaways:</span> {escape(ep_notes["takeaways"])}</div>'
            if note_parts:
                notes_html = f'<details class="episode-notes-toggle"><summary></summary>{note_parts}</details>'

            episodes_html += f"""<div class="episode">
  <img class="episode-art" src="{artwork_url}" alt="{escape(ep.get('podcast_title', ''))}" loading="lazy">
  <div class="episode-info">
    <div class="episode-podcast">{escape(ep.get('podcast_title', ''))}</div>
    <a class="episode-title" href="https://www.google.com/search?q={quote_plus(ep.get('podcast_title', '') + ' ' + ep.get('title', ''))}&amp;btnI" target="_blank" rel="noopener">{escape(ep.get('title', ''))}</a>
    <div class="episode-meta">
      {f'<span>{published}</span>' if published else ''}
      {f'<span>{duration_str}</span>' if duration_str else ''}
    </div>
    {notes_html}
  </div>
</div>
"""

    # Stats
    podcast_set = {ep.get("podcast_title") for ep in episodes}
    total_minutes = sum(ep.get("played_up_to", 0) or ep.get("duration", 0) for ep in episodes) // 60

    if total_minutes < 120:
        time_str = f"{total_minutes:,} min"
    elif total_minutes < 2 * 24 * 60:
        hours = total_minutes / 60
        time_str = f"{hours:.1f} hrs"
    else:
        days = total_minutes / (24 * 60)
        time_str = f"{days:.1f} days"

    # Average listening speed from user stats
    stats = data.get("stats", {})
    time_listened = int(stats.get("timeListened", 0))
    time_saved_speed = int(stats.get("timeVariableSpeed", 0))
    if time_listened > 0:
        avg_speed = (time_listened + time_saved_speed) / time_listened
        speed_str = f"""<div class="stat"><span class="stat-num">{avg_speed:.1f}x</span> avg speed</div>"""
    else:
        speed_str = ""

    stats_html = f"""
    <div class="stats">
      <div class="stat"><span class="stat-num">{len(episodes)}</span> episodes</div>
      <div class="stat"><span class="stat-num">{len(podcast_set)}</span> podcasts</div>
      <div class="stat"><span class="stat-num">{time_str}</span> listened</div>
      {speed_str}
    </div>
    """

    # Per-podcast stats
    podcast_stats: dict[str, dict] = {}
    for ep in episodes:
        name = ep.get("podcast_title", "Unknown")
        if name not in podcast_stats:
            podcast_stats[name] = {
                "episodes": 0,
                "time": 0,
                "first": None,
                "last": None,
                "podcast_uuid": ep.get("podcast_uuid", ""),
            }
        ps = podcast_stats[name]
        ps["episodes"] += 1
        ps["time"] += ep.get("played_up_to", 0) or ep.get("duration", 0)
        listened = ep.get("listened_date", "")
        if listened:
            if ps["first"] is None or listened < ps["first"]:
                ps["first"] = listened
            if ps["last"] is None or listened > ps["last"]:
                ps["last"] = listened

    ranked = sorted(podcast_stats.items(), key=lambda x: x[1]["time"], reverse=True)
    max_time = ranked[0][1]["time"] if ranked else 1

    def format_duration(seconds: int) -> str:
        mins = seconds // 60
        if mins < 120:
            return f"{mins} min"
        hours = mins / 60
        if hours < 48:
            return f"{hours:.1f} hrs"
        return f"{mins / (24 * 60):.1f} days"

    def format_date_short(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%b %Y")
        except (ValueError, AttributeError):
            return ""

    podcast_stats_html = '<div class="podcast-stats">\n'
    podcast_stats_html += '<h2 class="month-header" style="cursor:pointer;" onclick="this.nextElementSibling.classList.toggle(\'collapsed\')">Podcasts ▾</h2>\n'
    podcast_stats_html += '<div class="podcast-list">\n'
    for name, ps in ranked:
        pct = (ps["time"] / max_time) * 100
        artwork_url = f"https://static.pocketcasts.com/discover/images/webp/200/{ps['podcast_uuid']}.webp"
        date_range = format_date_short(ps["first"])
        last = format_date_short(ps["last"])
        if date_range and last and date_range != last:
            date_range = f"{date_range} – {last}"
        elif last:
            date_range = last

        podcast_stats_html += f"""<div class="podcast-row">
  <img class="podcast-row-art" src="{artwork_url}" alt="{escape(name)}" loading="lazy">
  <div class="podcast-row-info">
    <div class="podcast-row-name">{escape(name)}</div>
    <div class="podcast-row-meta">{ps['episodes']} ep · {format_duration(ps['time'])}{f' · {date_range}' if date_range else ''}</div>
    <div class="podcast-bar-bg"><div class="podcast-bar" style="width:{pct:.0f}%"></div></div>
  </div>
</div>
"""
    podcast_stats_html += '</div></div>\n'

    synced_str = ""
    if last_synced:
        try:
            synced_dt = datetime.fromisoformat(last_synced)
            synced_str = synced_dt.strftime("%B %d, %Y at %I:%M %p UTC")
        except (ValueError, AttributeError):
            synced_str = last_synced

    html = html_template.replace("{{EPISODES}}", episodes_html)
    html = html.replace("{{STATS}}", stats_html)
    html = html.replace("{{PODCAST_STATS}}", podcast_stats_html)
    html = html.replace("{{LAST_SYNCED}}", synced_str)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "index.html", "w") as f:
        f.write(html)

    print(f"Site built: {OUTPUT_DIR / 'index.html'}")


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


if __name__ == "__main__":
    build()
