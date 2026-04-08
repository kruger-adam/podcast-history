# Podcast History

A shareable webpage that automatically tracks your Pocket Casts listening history.

A GitHub Action syncs your history every 12 hours and deploys a static site to GitHub Pages.

## Setup

### 1. Create a GitHub repo

Create a new repo (public or private — GitHub Pages works with both) and push this code to it.

### 2. Add your Pocket Casts credentials as secrets

Go to **Settings → Secrets and variables → Actions** and add:

- `POCKETCASTS_EMAIL` — your Pocket Casts login email
- `POCKETCASTS_PASSWORD` — your Pocket Casts password

### 3. Enable GitHub Pages

Go to **Settings → Pages** and set:

- **Source**: "Deploy from a branch"
- **Branch**: `gh-pages` / `/ (root)`

### 4. Run it

The action runs automatically every 12 hours. To trigger it immediately:

Go to **Actions → "Sync Pocket Casts & Deploy" → Run workflow**

### 5. Share

Your page will be live at `https://<your-username>.github.io/<repo-name>/`

## Local development

```bash
# Set your credentials
export POCKETCASTS_EMAIL="you@example.com"
export POCKETCASTS_PASSWORD="your-password"

# Install deps
pip install -r requirements.txt

# Sync history
python sync.py

# Build site
python build_site.py

# Preview (Python's built-in server)
cd site && python -m http.server 8000
```

## How it works

1. `sync.py` authenticates with Pocket Casts, fetches your last 100 listened episodes, and merges any new ones into `data/history.json` with today's date as the "listened" timestamp
2. `build_site.py` renders that JSON into a static HTML page
3. The GitHub Action runs both on a 12-hour cron, commits new data, and deploys to GitHub Pages
