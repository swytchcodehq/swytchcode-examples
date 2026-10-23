"""The Trips sheet, read and written through Swytchcode.

The bridge holds no Google key: Swytchcode keeps the Google sign-in, and its
policies only let these tools touch the Trips sheet.
"""

import json
import os

import swy

CREATE = "google_sheets.spreadsheet.create"
READ = "google_sheets.value.get"
APPEND = "google_sheets.value.rangeappend.create"
WRITE = "google_sheets.valuesbatchupdate.create"
ADD_TAB = "google_sheets.spreadsheetidbatchupdate.create"

REQUEST_COLUMNS = ["id", "action", "from", "to", "date", "time", "cabin", "max_price",
                   "search", "option", "booking", "status", "result", "updated"]
OPTION_COLUMNS = ["search", "option", "offer", "airline", "departs", "arrives", "stops", "price"]
TRAVELLER_COLUMNS = ["title", "gender", "given_name", "family_name", "born_on", "email", "phone_number"]

# Written into the sheet's "How to use" tab, for the assistant to follow.
HOW_TO_USE = [
    "This sheet books flights. For each request, add one row to the Requests tab with status = new.",
    "Never change the Options tab, and never edit a row once its status has changed.",
    "",
    "To search: id = the next number, action = search, from and to = 3-letter airport or city codes",
    "(LHR, NYC), date = YYYY-MM-DD, time = morning / afternoon / evening / any,",
    "cabin = economy / premium economy / business / first, max_price = a number.",
    "",
    "To book: id = the next number, action = book, search = the id of the search row,",
    "option = 1, 2 or 3 from that search's result.",
    "",
    "To cancel: id = the next number, action = cancel, booking = the booking reference.",
    "",
    "Before the first booking, fill row 2 of the Traveller tab with the owner's details. Ask the owner for",
    "anything you don't know, and never guess: title = mr / ms / mrs / miss / dr, gender = m / f,",
    "given_name, family_name, born_on = YYYY-MM-DD, email, phone_number with the country code (+447700900123).",
    "",
    "After adding a row, wait about 15 seconds, then read that row's status and result, and tell the owner",
    "the result in your own words, keeping every price, time and booking reference exactly as written.",
    "",
    "status is one of:",
    "  working: wait a few seconds more.",
    "  done, booked, cancelled: finished.",
    "  waiting for approval: the owner approves it on their phone. Read the row again after the time in the result.",
    "  blocked: one of the owner's spending rules refused it.",
    "  failed: the result says what to fix. Fix it, then add a new row.",
    "  no answer: it wasn't approved in time. Add a new row to try again.",
]


class SheetsError(Exception):
    """Google Sheets didn't answer as expected. The bridge retries on its next check."""


def a1(row, col):
    """A1 notation for a 1-based row and column."""
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


class Spreadsheet:
    def __init__(self, sheet_id, url):
        self.id = sheet_id
        self.url = url

    def call(self, tool, args):
        # Every spreadsheetId is checked against TRIP_SHEET_ID by the policies.
        try:
            return swy.run(tool, {"spreadsheetId": self.id, **args},
                           env={"TRIP_SHEET_ID": self.id}, quiet=True)
        except (swy.Blocked, swy.Failed, swy.NeedsApproval) as e:
            raise SheetsError(f"{tool}: {e}") from e

    def worksheet(self, name):
        return Tab(self, name)

    def write(self, ranges):
        """Writes {range: rows} in one call."""
        self.call(WRITE, {"body": {"valueInputOption": "RAW", "data": [
            {"range": r, "values": values} for r, values in ranges.items()]}})


class Tab:
    def __init__(self, spreadsheet, name):
        self.spreadsheet = spreadsheet
        self.name = name

    def get_all_values(self):
        return self.spreadsheet.call(READ, {"range": f"'{self.name}'!A1:Z"}).get("values", [])

    def get_all_records(self):
        """Every row after the header, as {column: value}."""
        values = self.get_all_values()
        if not values:
            return []
        header = values[0]
        return [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in values[1:]]

    def append_rows(self, rows):
        self.spreadsheet.call(APPEND, {
            "range": f"'{self.name}'!A1",
            "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS",
            "body": {"values": [[str(c) for c in r] for r in rows]},
        })

    def update_cells(self, cells):
        """Writes {(row, col): value}, 1-based, in one call."""
        self.spreadsheet.write({f"'{self.name}'!{a1(r, c)}": [[v]] for (r, c), v in cells.items()})


def open_or_create(state_file):
    """The Trips sheet named in state_file, or a new one, which is then
    remembered there. Returns (sheet, created)."""
    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)
        return Spreadsheet(state["id"], state["url"]), False

    try:
        made = swy.run(CREATE, {"body": {
            "properties": {"title": "Trips"},
            "sheets": [{"properties": {"title": t}} for t in ("Requests", "Options", "Traveller", "How to use")],
        }}, env={"TRIP_SHEET_ID": "none"}, quiet=True)
    except (swy.Blocked, swy.Failed, swy.NeedsApproval) as e:
        raise SheetsError(f"{CREATE}: {e}") from e
    sheet = Spreadsheet(made["spreadsheetId"], made["spreadsheetUrl"])
    sheet.write({"Requests!A1": [REQUEST_COLUMNS], "Options!A1": [OPTION_COLUMNS]})
    os.makedirs(os.path.dirname(os.path.abspath(state_file)), exist_ok=True)
    with open(state_file, "w") as f:
        json.dump({"id": sheet.id, "url": sheet.url}, f)
    return sheet, True


def update_layout(sheet):
    """Brings a sheet made by an older bridge up to date: the Traveller tab and
    the current How to use text. Safe to run on every start."""
    try:
        sheet.call(ADD_TAB, {"body": {"requests": [{"addSheet": {"properties": {"title": "Traveller"}}}]}})
    except SheetsError as e:
        if "already exists" not in str(e):
            raise
    # Clear old How to use lines past the end of the current text.
    lines = HOW_TO_USE + [""] * 10
    sheet.write({"Traveller!A1": [TRAVELLER_COLUMNS], "'How to use'!A1": [[line] for line in lines]})
