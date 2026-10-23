"""Duffel offers and orders, in words. Both have the same slices and prices."""

import datetime as dt


def departs(offer):
    return offer["slices"][0]["segments"][0]["departing_at"]


def airline(offer):
    first = offer["slices"][0]["segments"][0]
    carrier = first.get("operating_carrier") or first.get("marketing_carrier") or offer.get("owner") or {}
    return carrier.get("name", "")


def price(offer):
    return f'{offer["total_amount"]} {offer["total_currency"]}'


def times(offer):
    """'09:15 to 17:20', with (+1) when it lands the next day."""
    segments = offer["slices"][0]["segments"]
    leave, land = segments[0]["departing_at"], segments[-1]["arriving_at"]
    days = (dt.date.fromisoformat(land[:10]) - dt.date.fromisoformat(leave[:10])).days
    return f'{leave[11:16]} to {land[11:16]}{f" (+{days})" if days else ""}'


def option(offer):
    """One search result: 'Iberia, 09:15 to 17:20, nonstop, 215.62 USD'."""
    stops = len(offer["slices"][0]["segments"]) - 1
    return f'{airline(offer)}, {times(offer)}, {plural(stops, "stop") if stops else "nonstop"}, {price(offer)}'


def flight(offer):
    """A flight in one line: 'Iberia LHR to JFK, Sat 24 Oct, 09:15 to 17:20'."""
    segments = offer["slices"][0]["segments"]
    day = dt.date.fromisoformat(departs(offer)[:10])
    return (f'{airline(offer)} {segments[0]["origin"]["iata_code"]} to '
            f'{segments[-1]["destination"]["iata_code"]}, {day:%a %-d %b}, {times(offer)}')


def passenger(order):
    p = order["passengers"][0]
    return f'{p.get("given_name", "")} {p.get("family_name", "")}'.strip()


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"
