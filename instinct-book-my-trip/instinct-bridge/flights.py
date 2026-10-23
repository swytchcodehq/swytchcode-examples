"""Search, book and cancel flights on Duffel, through Swytchcode.

Each action takes a row from the Requests tab and returns an Update: the
row's new status, the result for the assistant to read out, and, for
bookings, what goes in the booking cell.
"""

import datetime as dt
import os
import re
import secrets
import time
from typing import NamedTuple, Optional

import checks
import confirmation
import describe
import swy
from checks import RowError, cell
from describe import departs, flight, plural, price

# The Duffel tools, as `swytchcode list` shows them after `swytchcode get duffel`.
TOOLS = {
    "search": "duffel_flights.offer_request.create",
    "offer": "duffel_flights.offer.get",
    "book": "duffel_flights.order.create",
    "orders": "duffel_flights.order.list",
    "quote": "duffel_flights.order_cancellation.create",
    "cancel": "duffel_flights.order_cancellation.confirm.create",
}
DUFFEL_VERSION = {"Duffel-Version": "v2"}

# Where the workspace sends approvals (set in the Swytchcode app), for messages.
APPROVAL_APP = os.environ.get("APPROVAL_APP", "Slack")
# How often Swytchcode's approval watcher checks for your decision.
APPROVAL_CHECK_SECONDS = 120
# How long to wait for an approval before giving up. Keep it a little above
# the approval_timeout in policies.json.
APPROVAL_WAIT_SECONDS = int(os.environ.get("APPROVAL_WAIT_SECONDS", "720"))
# Rows waiting for approval are looked up in Duffel this often.
WAITING_CHECK_SECONDS = float(os.environ.get("WAITING_CHECK_SECONDS", "10"))

WAITING = "waiting for approval"


class Update(NamedTuple):
    status: str
    result: str
    booking: Optional[str] = None  # None leaves the booking cell as it is


def duffel(tool, args):
    """One Duffel call. Returns Duffel's `data`."""
    body = swy.run(TOOLS[tool], {**args, **DUFFEL_VERSION})
    return body["data"] if isinstance(body, dict) and "data" in body else body


# ── Search ───────────────────────────────────────────────────────────────────

def search(row, options_tab):
    q = checks.search(row)
    leg = {"origin": q["origin"], "destination": q["destination"], "departure_date": q["date"].isoformat()}
    if q["window"]:
        leg["departure_time"] = {"from": q["window"][0], "to": q["window"][1]}
    try:
        found = duffel("search", {
            "body": {"data": {"slices": [leg], "passengers": [{"type": "adult"}], "cabin_class": q["cabin"]}},
            "return_offers": True,
            "supplier_timeout": 10000,
        })
    except swy.NeedsApproval:
        raise RowError("Searches shouldn't need approval. Check the rules in policies.json.") from None

    offers = found.get("offers") or []
    if q["max_price"] is not None:
        offers = [o for o in offers if float(o["total_amount"]) <= q["max_price"]]
    offers.sort(key=lambda o: float(o["total_amount"]))
    route = f'{q["origin"]} to {q["destination"]} on {q["date"]:%a %-d %b}'
    if not offers:
        limit = f' under ${q["max_price"]:g}' if q["max_price"] is not None else ""
        return Update("done", f"No flights from {route}{limit}. Try another date, or a higher max_price.")

    # Duffel's test mode ignores departure_time, so check the time window here too.
    note = ""
    if q["window"]:
        in_window = [o for o in offers if q["window"][0] <= departs(o)[11:16] <= q["window"][1]]
        if in_window:
            offers = in_window
        else:
            note = f'Nothing leaves in the {q["time"]}, so these are the cheapest at any time. '
    offers = offers[:3]
    options_tab.append_rows([option_row(row["id"], n, o) for n, o in enumerate(offers, 1)])
    listing = " ".join(f"Option {n}: {describe.option(o)}." for n, o in enumerate(offers, 1))
    return Update("done", f"{note}{plural(len(offers), 'flight')} from {route}. {listing}")


def option_row(search_id, n, offer):
    segments = offer["slices"][0]["segments"]
    return [search_id, n, offer["id"], describe.airline(offer), departs(offer).replace("T", " ")[:16],
            segments[-1]["arriving_at"].replace("T", " ")[:16], len(segments) - 1, price(offer)]


# ── Book ─────────────────────────────────────────────────────────────────────

def book(row, sheet, fallback_traveller=None):
    passenger = checks.traveller(first_record(sheet, "Traveller")) or fallback_traveller
    if not passenger:
        raise RowError("I need the traveller's details first: title, first and last name, gender, date of "
                       "birth, email and phone number. Put them in row 2 of the Traveller tab, then ask again.")
    offer_id = find_offer(sheet, *checks.option(row))
    # Prices change and offers expire, so book at the current price.
    offer = duffel("offer", {"id": offer_id})
    # The booking finishes in the background after you approve it, so tag it
    # to find it again. The tag also records when approval was asked for.
    tag = f"pending-{int(time.time())}-{secrets.token_hex(3)}"
    try:
        order = duffel("book", {"body": {"data": {
            "type": "instant",
            "selected_offers": [offer_id],
            "passengers": [{**passenger, "id": offer["passengers"][0]["id"]}],
            "payments": [{"type": "balance", "amount": offer["total_amount"], "currency": offer["total_currency"]}],
            # flight is shown on the approval request.
            "metadata": {"sheet_request": tag, "flight": flight(offer)},
        }}})
    except swy.NeedsApproval as e:
        if not e.delivered:
            return Update(WAITING, f"This booking needs your OK, but Swytchcode can't reach {APPROVAL_APP} yet. "
                                   "It keeps trying, and nothing is booked until you approve.", tag)
        who = f'{passenger["given_name"]} {passenger["family_name"]}'
        return Update(WAITING, f"Approve it in {APPROVAL_APP}: {flight(offer)}, {price(offer)}, for {who}. "
                               f"Once you do, it's booked by {eta(time.time())}.", tag)
    return booked(order)


def find_offer(sheet, search_id, number):
    """The offer for (search, option), from the rows the bridge itself wrote."""
    for opt in sheet.worksheet("Options").get_all_records():
        if str(opt["search"]) == search_id and str(opt["option"]) == number:
            if checks.OFFER_ID.match(str(opt["offer"])):
                return str(opt["offer"])
    raise RowError(f"Search {search_id} has no option {number}. Check the Options tab.")


def booked(order):
    """The update for a finished booking, after emailing the confirmation."""
    test = "" if order.get("live_mode") else " (test booking, not a real ticket)"
    text = (f'Booked{test}. Reference {order["booking_reference"]}: {flight(order)}, {price(order)}, '
            f'for {describe.passenger(order)}. {confirmation.send(order)}')
    return Update("booked", text, order["booking_reference"])


# ── Cancel ───────────────────────────────────────────────────────────────────

def cancel(row):
    ref = checks.booking_ref(row)
    order = order_by_reference(ref)
    if order.get("cancelled_at"):
        return Update("done", f"{ref} is already cancelled.")
    quote = duffel("quote", {"body": {"data": {"order_id": order["id"]}}})
    refund = f'{quote.get("refund_amount") or "?"} {quote.get("refund_currency") or ""}'.strip()
    try:
        duffel("cancel", {"id": quote["id"]})
    except swy.NeedsApproval as e:
        reach = "" if e.delivered else f" (Swytchcode can't reach {APPROVAL_APP} yet, but keeps trying)"
        return Update(WAITING, f"Approve it in {APPROVAL_APP}{reach}: cancel {ref}, {flight(order)}, refund "
                               f"{refund}. Once you do, it's cancelled by {eta(time.time())}.",
                      f"{ref} pending-{int(time.time())}")
    return Update("cancelled", f"Cancelled {ref}. Refund: {refund}.", ref)


def order_by_reference(ref):
    orders = duffel("orders", {"booking_reference": ref})
    if not orders:
        raise RowError(f"There's no booking with reference {ref}.")
    return orders[0]


# ── Waiting for approval ─────────────────────────────────────────────────────

def follow_up(row):
    """The next update for a row waiting for approval, or None for no change.

    Once approved, Swytchcode makes the call in the background and this script
    never sees the reply, so it looks the result up in Duffel instead.
    """
    is_book = cell(row, "action").lower() == "book"
    if is_book:
        tag = cell(row, "booking")
        for order in duffel("orders", {"limit": 50}) or []:
            if (order.get("metadata") or {}).get("sheet_request") == tag:
                return booked(order)
    else:
        ref = cell(row, "booking").split()[0].upper()
        if order_by_reference(ref).get("cancelled_at"):
            return Update("cancelled", f"Cancelled {ref}.", ref)

    asked = asked_at(row)
    if not asked:
        return None
    done = "booked" if is_book else "cancelled"
    if time.time() - asked > APPROVAL_WAIT_SECONDS:
        return Update("no answer", f"It wasn't approved in time, or it was denied, so nothing was {done}. "
                                   "Ask again if you still want it.")
    when = eta(asked)
    if when in cell(row, "result"):
        return None
    return Update(WAITING, f"Still waiting for your OK in {APPROVAL_APP}. If you've approved, it's {done} by {when}.")


def asked_at(row):
    """When approval was asked for, from the tag in the booking cell (0 if unknown)."""
    match = re.search(r"pending-(\d{9,})", cell(row, "booking"))
    return int(match.group(1)) if match else 0


def eta(asked, now=None):
    """When an approval given by now will have gone through, as local HH:MM.

    Swytchcode's approval watcher checks for your decision 2 minutes after the
    request and every 2 minutes after that, so the call runs at the first check
    after you approve, plus a little for this script to notice.
    """
    now = time.time() if now is None else now
    checks_done = max(1, int((now - asked) // APPROVAL_CHECK_SECONDS) + 1)
    at = asked + checks_done * APPROVAL_CHECK_SECONDS + WAITING_CHECK_SECONDS + 30
    return f"{dt.datetime.fromtimestamp(at).astimezone():%H:%M %Z}"


def first_record(sheet, tab):
    records = sheet.worksheet(tab).get_all_records()
    return records[0] if records else None
