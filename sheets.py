#!/usr/bin/env python3
"""Sync episodes to a Google Sheet and read notes back."""

import json
import os
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

DATA_FILE = Path(__file__).parent / "data" / "history.json"
NOTES_FILE = Path(__file__).parent / "data" / "notes.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_client() -> gspread.Client:
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("Set GOOGLE_SERVICE_ACCOUNT_JSON env var", file=sys.stderr)
        sys.exit(1)
    creds_data = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    return gspread.authorize(creds)


def sync_sheet():
    spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not spreadsheet_id:
        print("Set GOOGLE_SHEET_ID env var", file=sys.stderr)
        sys.exit(1)

    if not DATA_FILE.exists():
        print("No history data found. Run sync.py first.")
        return

    with open(DATA_FILE) as f:
        data = json.load(f)

    episodes = data["episodes"]
    # Same filter as build_site.py — only episodes with >= 60s played
    episodes = [ep for ep in episodes if (ep.get("played_up_to", 0) or ep.get("duration", 0)) >= 60]

    client = get_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    # Get or create the "Episodes" sheet
    try:
        worksheet = spreadsheet.worksheet("Episodes")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet("Episodes", rows=1000, cols=6)
        worksheet.update("A1:F1", [["UUID", "Podcast", "Episode", "Date", "Why I Listened", "Takeaways"]])
        worksheet.format("A1:F1", {"textFormat": {"bold": True}})
        # Hide the UUID column
        spreadsheet.batch_update({
            "requests": [{
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                }
            }]
        })
        print("Created 'Episodes' sheet with headers")

    # Read existing rows to find which episodes are already in the sheet
    all_values = worksheet.get_all_values()
    existing_uuids = {row[0] for row in all_values[1:]} if len(all_values) > 1 else set()

    # Find new episodes to add
    new_rows = []
    for ep in episodes:
        uuid = ep.get("uuid", "")
        if uuid and uuid not in existing_uuids:
            listened = ep.get("listened_date", "")
            date_str = ""
            if listened:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(listened)
                    date_str = dt.strftime("%Y-%m-%d")
                except (ValueError, AttributeError):
                    date_str = listened
            new_rows.append([
                uuid,
                ep.get("podcast_title", ""),
                ep.get("title", ""),
                date_str,
                "",  # Why I Listened — blank for user to fill in
                "",  # Takeaways — blank for user to fill in
            ])

    if new_rows:
        # Sort new rows by date descending so newest episodes appear at top
        new_rows.sort(key=lambda r: r[3], reverse=True)
        # Insert after header row (row 2) so new episodes appear at top
        worksheet.insert_rows(new_rows, row=2)
        print(f"Added {len(new_rows)} new episode(s) to sheet")
    else:
        print("No new episodes to add to sheet")

    # Read back all notes (re-fetch after insert)
    all_values = worksheet.get_all_values()
    notes = {}
    for row in all_values[1:]:
        if len(row) >= 6:
            uuid = row[0]
            reason = row[4].strip() if row[4] else ""
            takeaways = row[5].strip() if row[5] else ""
            if uuid and (reason or takeaways):
                note = {}
                if reason:
                    note["reason"] = reason
                if takeaways:
                    note["takeaways"] = takeaways
                notes[uuid] = note

    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)

    print(f"Read {len(notes)} note(s) from sheet")


if __name__ == "__main__":
    sync_sheet()
