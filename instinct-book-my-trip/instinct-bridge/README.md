# Instinct bridge

[Instinct](https://instinct.com) can't connect to custom servers or APIs, but it can write to a Google Sheet. So Instinct writes your flight requests into a sheet, this bridge runs them through Swytchcode, and Instinct reads the answers back to you on WhatsApp.

```
You (WhatsApp) -> Instinct -> Google Sheet -> bridge -> Swytchcode -> Duffel (flights)
                     ^                          |                  -> Resend (confirmation email)
                     +--- reads the answer <----+     approvals: Slack or Telegram
```

The bridge holds no keys. The Duffel key, the Google sign-in and the Resend key all stay in Swytchcode, and every call goes through the rules in [`policies.json`](../.swytchcode/integrations/policies.json).

It works the same with any assistant that can write to a Google Sheet.

## Setup (about 10 minutes)

You need [Docker](https://docs.docker.com/get-docker/). Then:

```bash
cd instinct-book-my-trip/instinct-bridge
./setup.sh
```

It walks you through six steps, and skips any you've already done:

1. Builds the bridge.
2. Swytchcode sign-in (a link).
3. Duffel test key (free, 2 minutes; the script shows where to get it).
4. Google sign-in (a link). Use the Google account your assistant uses.
5. Resend API key, for confirmation emails (free).
6. Where approvals go: pick Slack or Telegram for the `book-my-trip` workspace in [app.swytchcode.com](https://app.swytchcode.com) (Settings, Workspaces, HITL Notifications).

At the end it starts the bridge, which makes a sheet called **Trips** in your Google Drive. It prints the sheet's link and the message to send Instinct.

## Try it

- *"Find me a flight from London to New York on 30 October under $500."* Three options.
- *"Book option 1."* Over $100, so an approval request arrives in Slack or Telegram. Approve it, and within about 2 minutes it's booked and a confirmation email goes out.
- Book something over $300, and it's blocked: "Over your $300 per ticket limit".
- *"Cancel my booking."* That needs your approval too.

## The rules

All of them are in [`policies.json`](../.swytchcode/integrations/policies.json), and `swytchcode policy validate` tests them:

- **Only the calls the bridge needs** (13 of them). Everything else Duffel, Google Sheets and Resend can do is blocked.
- **Only its own Trips sheet:** no other sheet in your Google account.
- **No ticket over $300, no more than $500 or 2 bookings a day,** and only flights a search actually returned.
- **Bookings over $100 and all cancellations wait for your approval.** The approval names the passenger.
- **No more than 10 emails a day.**

## Keeping it safe

- **No keys are in the sheet or the bridge.** The traveller's details (name, date of birth, email, phone) are in the Traveller tab of your own sheet, in your own Google account. The bridge checks every field before booking.
- **Treat the sheet as untrusted:** anyone who can edit it can add a row. The bridge accepts only search, book and cancel, checks every cell, and books only options it found itself. Every booking still has to pass the rules and, over $100, your approval.
- Until you verify a domain in Resend, Resend only delivers to your own Resend address, so use that as the traveller's email.

## The code

| File | What it does |
| --- | --- |
| `bridge.py` | Watches the Requests tab and writes each result back |
| `flights.py` | Search, book and cancel on Duffel, and following up on approvals |
| `checks.py` | Checks every cell from the sheet before it's used |
| `confirmation.py` | The booking email, through Resend |
| `sheets.py` | Reads and writes the Trips sheet, and its How to use text |
| `describe.py` | Puts flights into words for the sheet and the email |
| `swy.py` | Runs every call through Swytchcode: worked, blocked, waiting for approval or failed |

Every call to Duffel, Google and Resend goes through `swy.run()`, so there are no API keys or HTTP clients anywhere else.

## Good to know

- **After you approve, the booking takes up to 2 minutes.** Swytchcode checks for your decision every 2 minutes.
- Duffel's test mode ignores the departure time you ask for, so the bridge filters by time itself. When nothing matches, it says so and shows the cheapest at any time.
- Logs: `docker compose logs -f bridge`. Test without Google: `docker compose run --rm bridge python check.py`.
