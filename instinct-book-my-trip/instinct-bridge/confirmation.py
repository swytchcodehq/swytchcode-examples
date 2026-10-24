"""The booking confirmation email, sent through Resend via Swytchcode.

A failed email never undoes a booking: send() only returns a sentence for the
row's result, saying where the email went or why it didn't.
"""

import html
import os
import re

import describe
import swy

TOOL = "resend.email.create"
# With Resend's test sender, mail only reaches your own Resend account's address.
FROM = os.environ.get("EMAIL_FROM", "Book My Trip <onboarding@resend.dev>")


def send(order):
    to = order["passengers"][0].get("email")
    if not to:
        return "There's no email address to send a confirmation to."
    test = not order.get("live_mode")
    ref = order["booking_reference"]
    ticket = next((d["unique_identifier"] for d in order.get("documents") or []
                   if d.get("type") == "electronic_ticket"), "not issued yet")
    details = [
        ("Booking reference", ref),
        ("Passenger", describe.passenger(order)),
        ("Flight", describe.flight(order)),
        ("Price", describe.price(order)),
        ("E-ticket", ticket),
    ]
    heading = "Your flight is booked" + (" (test booking, not a real ticket)" if test else "")
    try:
        swy.run(TOOL, {"body": {
            "from": FROM,
            "to": [to],
            "subject": f"Flight booked: {ref}" + (" (test)" if test else ""),
            "html": html_body(heading, details),
            "text": f"{heading}.\n\n" + "\n".join(f"{k}: {v}" for k, v in details),
        }})
    except swy.NeedsApproval:
        return "The confirmation email is waiting for approval."
    except (swy.Blocked, swy.Failed) as e:
        return f"The confirmation email wasn't sent: {explain(str(e))}"
    return f"Confirmation emailed to {to}."


def html_body(heading, details):
    rows = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:#666">{html.escape(k)}</td>'
        f'<td style="padding:6px 0"><b>{html.escape(str(v))}</b></td></tr>'
        for k, v in details)
    return (f'<div style="font-family:sans-serif;font-size:15px">'
            f'<h2 style="font-weight:600">{html.escape(heading)}</h2><table>{rows}</table>'
            f'<p style="color:#888;font-size:13px">Booked from a Google Sheet, through Swytchcode.</p></div>')


def explain(error):
    """Resend's errors, in words the traveller can act on."""
    own = re.search(r"only send testing emails to your own email address \(([^)]+)\)", error)
    if own:
        return (f"Resend's test sender only delivers to your Resend sign-up address, {own.group(1)}. "
                "Use that as the traveller's email, or verify a domain in Resend.")
    return error.rstrip(".") + "."
