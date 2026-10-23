"""Instinct bridge: book flights from a Google Sheet through Swytchcode.

Instinct (or any assistant that can write to a Google Sheet) adds a row to the
Requests tab. This script picks it up, makes the calls through Swytchcode, and
writes the result back for the assistant to read out.

    sheets.py        the Trips sheet
    checks.py        checks every cell, since anyone who can edit the sheet can write anything
    flights.py       search, book and cancel on Duffel
    confirmation.py  the booking email, through Resend
    swy.py           runs each call through Swytchcode, which holds the keys and applies policies.json
"""

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import checks  # noqa: E402  (these read settings from .env)
import flights  # noqa: E402
import sheets  # noqa: E402
import swy  # noqa: E402
from checks import RowError, cell  # noqa: E402
from flights import Update  # noqa: E402
from swy import log  # noqa: E402

# Where the bridge remembers the Trips sheet it made.
SHEET_FILE = os.environ.get("SHEET_FILE", "trips-sheet.json")
# A passenger to book when the Traveller tab is empty (optional).
TRAVELLER_FILE = os.environ.get("TRAVELLER_FILE", "traveller.json")
# Each check is one Sheets read. Google allows 60 reads a minute, so don't go below 2.
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "2"))

# How a policy refusal starts, by action.
BLOCKED = {"search": "Search blocked", "book": "Not booked", "cancel": "Not cancelled"}


class Bridge:
    def __init__(self, sheet, traveller=None):
        self.sheet = sheet
        self.requests = sheet.worksheet("Requests")
        self.traveller = traveller
        self.header = None
        self.last_follow_up = {}  # row number -> when it was last looked up in Duffel

    def tick(self):
        """One pass over the Requests tab."""
        values = self.requests.get_all_values()
        if not values:
            return
        self.header = values[0]
        for n, cells in enumerate(values[1:], start=2):
            row = dict(zip(self.header, cells + [""] * (len(self.header) - len(cells))))
            row["id"] = row.get("id") or n  # a row without an id goes by its row number
            status = cell(row, "status").lower()
            if status == "new":
                self.start(n, row)
            elif status == flights.WAITING:
                self.follow_up(n, row)

    def start(self, n, row):
        """Runs a new row."""
        name = cell(row, "action").lower()
        log(f"row {row['id']}: {name}")
        try:
            self.write(n, Update("working", ""))
            name = checks.action(row)
            if name == "search":
                update = flights.search(row, self.sheet.worksheet("Options"))
            elif name == "book":
                update = flights.book(row, self.sheet, self.traveller)
            else:
                update = flights.cancel(row)
        except swy.Blocked as e:
            update = Update("blocked", f"{BLOCKED[name]}. {sentence(str(e))}")
        except (RowError, swy.Failed) as e:
            update = Update("failed", sentence(str(e)))
        except sheets.SheetsError as e:
            log(f"row {row['id']}: {e}")
            update = Update("failed", "Couldn't read the sheet just then. Add the row again.")
        log(f"row {row['id']}: {update.status}: {update.result}")
        self.write(n, update)

    def follow_up(self, n, row):
        """Checks a row waiting for approval, every WAITING_CHECK_SECONDS."""
        if time.monotonic() - self.last_follow_up.get(n, 0) < flights.WAITING_CHECK_SECONDS:
            return
        self.last_follow_up[n] = time.monotonic()
        try:
            update = flights.follow_up(row)
        except (RowError, swy.Blocked, swy.Failed, swy.NeedsApproval) as e:
            log(f"row {row['id']}: couldn't check on it yet: {e}")
            return
        if update:
            log(f"row {row['id']}: {update.status}: {update.result}")
            self.write(n, update)

    def write(self, n, update):
        col = {name: i + 1 for i, name in enumerate(self.header)}
        now = dt.datetime.now().astimezone()
        cells = {(n, col["status"]): update.status,
                 (n, col["result"]): update.result[:500],
                 (n, col["updated"]): f"{now:%Y-%m-%d %H:%M %Z}"}
        if update.booking is not None:
            cells[(n, col["booking"])] = update.booking
        self.requests.update_cells(cells)


def sentence(text):
    text = text.strip()
    text = text[:1].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def open_sheet():
    """The Trips sheet, made on the first run."""
    sheet, created = sheets.open_or_create(SHEET_FILE)
    if created:
        log(f"Made your Trips sheet: {sheet.url}")
    sheets.update_layout(sheet)
    header = sheet.worksheet("Requests").get_all_values()[0]
    missing = [c for c in sheets.REQUEST_COLUMNS if c not in header]
    if missing:
        sys.exit(f"The Requests tab is missing columns: {', '.join(missing)}.")
    return sheet


def load_traveller():
    path = Path(TRAVELLER_FILE)
    return checks.traveller(json.loads(path.read_text())) if path.exists() else None


def main():
    bridge = Bridge(open_sheet(), load_traveller())
    log(f"Watching {bridge.sheet.url} every {POLL_SECONDS:g}s. Ctrl+C to stop.")
    while True:
        try:
            bridge.tick()
        except sheets.SheetsError as e:
            log(f"Google Sheets didn't answer, trying again: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
