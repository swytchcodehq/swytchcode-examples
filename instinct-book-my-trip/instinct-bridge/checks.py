"""Checks on everything read from the sheet.

The sheet is untrusted: anyone with edit access can write anything in it. So
every cell is checked before it's used, and only checked values reach an API.
A RowError's message goes back into the row, for the assistant to read out,
so it says what to fix.
"""

import datetime as dt
import re

TIME_WINDOWS = {
    "morning": ("05:00", "11:59"),
    "afternoon": ("12:00", "17:59"),
    "evening": ("18:00", "23:59"),
    "any": None,
}
CABINS = {"economy", "premium_economy", "business", "first"}
TITLES = {"mr", "ms", "mrs", "miss", "dr"}
GENDERS = {"m": "m", "male": "m", "f": "f", "female": "f"}

AIRPORT = re.compile(r"^[A-Z]{3}$")
BOOKING_REF = re.compile(r"^[A-Z0-9]{5,8}$")
OFFER_ID = re.compile(r"^off_[A-Za-z0-9]+$")
NAME = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,49}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^\+[1-9]\d{6,14}$")


class RowError(Exception):
    """A row the bridge won't run. The message is written back to the row."""


def cell(row, name):
    return str(row.get(name, "")).strip()


def action(row):
    name = cell(row, "action").lower()
    if name not in ("search", "book", "cancel"):
        raise RowError("Set 'action' to search, book or cancel.")
    return name


def search(row):
    """The search a row asks for: route, date, time window, cabin and price limit."""
    window = (cell(row, "time") or "any").lower()
    if window not in TIME_WINDOWS:
        raise RowError("Set 'time' to morning, afternoon, evening or any.")
    cabin = (cell(row, "cabin") or "economy").lower().replace(" ", "_")
    if cabin not in CABINS:
        raise RowError("Set 'cabin' to economy, premium economy, business or first.")
    return {
        "origin": airport(row, "from"),
        "destination": airport(row, "to"),
        "date": travel_date(row),
        "time": window,
        "window": TIME_WINDOWS[window],
        "cabin": cabin,
        "max_price": max_price(row),
    }


def airport(row, name):
    code = cell(row, name).upper()
    if not AIRPORT.match(code):
        raise RowError(f"Set '{name}' to a 3-letter airport or city code, like LHR or NYC.")
    return code


def travel_date(row):
    try:
        day = dt.date.fromisoformat(cell(row, "date"))
    except ValueError:
        raise RowError("Write 'date' as YYYY-MM-DD, like 2026-12-18.") from None
    today = dt.date.today()
    if not today <= day <= today + dt.timedelta(days=330):
        raise RowError("Pick a 'date' between today and 330 days from now.")
    return day


def max_price(row):
    text = cell(row, "max_price").lstrip("$").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        raise RowError("Write 'max_price' as a number, like 400.") from None


def option(row):
    """The (search id, option number) a book row points at."""
    search_id, number = cell(row, "search"), cell(row, "option")
    if not search_id or not number.isdigit():
        raise RowError("To book, set 'search' to the search row's id and 'option' to 1, 2 or 3.")
    return search_id, number


def booking_ref(row):
    ref = cell(row, "booking").upper()
    if not BOOKING_REF.match(ref):
        raise RowError("To cancel, set 'booking' to the booking reference, like LFZKJJ.")
    return ref


def traveller(record):
    """The passenger from row 2 of the Traveller tab, in Duffel's format, or
    None when that row is empty."""
    t = {k: str(v).strip() for k, v in (record or {}).items()}
    if not any(t.values()):
        return None
    title = t.get("title", "").lower().rstrip(".")
    if title not in TITLES:
        raise RowError("In the Traveller tab, set 'title' to mr, ms, mrs, miss or dr.")
    gender = GENDERS.get(t.get("gender", "").lower())
    if not gender:
        raise RowError("In the Traveller tab, set 'gender' to m or f.")
    for name in ("given_name", "family_name"):
        if not NAME.match(t.get(name, "")):
            raise RowError(f"In the Traveller tab, write '{name}' in letters only, as on the passport.")
    try:
        born = dt.date.fromisoformat(t.get("born_on", ""))
    except ValueError:
        raise RowError("In the Traveller tab, write 'born_on' as YYYY-MM-DD, like 1990-04-12.") from None
    if not dt.date(1900, 1, 1) < born < dt.date.today():
        raise RowError("In the Traveller tab, 'born_on' isn't a real date of birth.")
    if not EMAIL.match(t.get("email", "")):
        raise RowError("In the Traveller tab, 'email' isn't an email address.")
    phone = re.sub(r"[\s()-]", "", t.get("phone_number", ""))
    if not PHONE.match(phone):
        raise RowError("In the Traveller tab, write 'phone_number' with the country code, like +447700900123.")
    return {"title": title, "gender": gender, "given_name": t["given_name"], "family_name": t["family_name"],
            "born_on": born.isoformat(), "email": t["email"], "phone_number": phone}
