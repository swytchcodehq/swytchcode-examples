"""Check the setup without Google: search, then book option 1 through
Swytchcode, with an in-memory sheet in place of the Google Sheet.

    python check.py LHR JFK 2026-11-06

It runs the same code as bridge.py, against Duffel test mode. A booking over
$100 waits for your approval in Slack or Telegram; approve it to see it go
through.
"""

import json
import sys
import time
from pathlib import Path

import bridge
import sheets


class Tab:
    def __init__(self, header):
        self.rows = [list(header)]

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def get_all_records(self):
        return [dict(zip(self.rows[0], r)) for r in self.rows[1:]]

    def append_rows(self, rows):
        self.rows += [[str(c) for c in r] for r in rows]

    def update_cells(self, cells):
        for (r, c), value in cells.items():
            self.rows[r - 1][c - 1] = value


class Sheet:
    url = "in-memory sheet"

    def __init__(self):
        self.tabs = {"Requests": Tab(sheets.REQUEST_COLUMNS), "Options": Tab(sheets.OPTION_COLUMNS),
                     "Traveller": Tab(sheets.TRAVELLER_COLUMNS)}

    def worksheet(self, name):
        return self.tabs[name]


def main():
    args = sys.argv[1:]
    origin = args[0] if len(args) > 0 else "LHR"
    destination = args[1] if len(args) > 1 else "JFK"
    date = args[2] if len(args) > 2 else time.strftime("%Y-%m-%d", time.localtime(time.time() + 14 * 86400))
    traveller = bridge.load_traveller() or json.loads(Path(__file__).with_name("traveller.json.example").read_text())
    sheet = Sheet()
    requests = sheet.tabs["Requests"]
    b = bridge.Bridge(sheet, traveller)

    def add(**cells):
        requests.rows.append([str(cells.get(c, "")) for c in sheets.REQUEST_COLUMNS])
        b.tick()
        row = requests.get_all_records()[-1]
        print(f"\n  {row['status']}: {row['result']}\n")
        return row

    print(f"1. Search {origin} to {destination} on {date}")
    row = add(id=1, action="search", **{"from": origin, "to": destination},
              date=date, time="any", max_price=500, status="new")
    if row["status"] != "done" or not sheet.tabs["Options"].get_all_records():
        sys.exit("Nothing to book. Fix what it says above, or try another date or route.")

    print("2. Book option 1")
    row = add(id=2, action="book", search=1, option=1, status="new")
    pending = (bridge.flights.WAITING, bridge.flights.CHECKING)
    if row["status"] not in pending:
        return

    step = "Looking it up in Duffel" if row["status"] == bridge.flights.CHECKING else \
        f"Approve it in {bridge.flights.APPROVAL_APP}"
    print(f"3. {step}. Checking every 10 seconds (Ctrl+C to stop).")
    while row["status"] in pending:
        time.sleep(10)
        b.tick()
        row = requests.get_all_records()[-1]
        print(f"   {time.strftime('%H:%M:%S')}  {row['status']}: {row['result']}")
    print("\nDone. Everything works: connect the Google Sheet next.")


if __name__ == "__main__":
    main()
