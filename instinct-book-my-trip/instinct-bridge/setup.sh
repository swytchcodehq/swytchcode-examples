#!/usr/bin/env bash
# One-time setup for the Instinct bridge. Safe to run again: finished steps are skipped.
set -euo pipefail
cd "$(dirname "$0")"

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
swy() { docker compose run --rm bridge swytchcode "$@"; }
quiet() { docker compose run --rm -T bridge swytchcode "$@" 2>/dev/null || true; }

command -v docker >/dev/null || { echo "Install Docker first: https://docs.docker.com/get-docker/"; exit 1; }

bold "1/6  Building (first time takes a couple of minutes)"
docker compose build --quiet

bold "2/6  Sign in to Swytchcode"
if quiet whoami | grep -q '^email:'; then
  echo "Already signed in as $(quiet whoami | awk '/^email:/{print $2}')."
else
  echo "A link opens the sign-in. Free account is fine."
  swy login
fi
# The project names its workspace in tooling.json: make it in this account if it's new.
quiet workspace use book-my-trip --create >/dev/null

bold "3/6  Connect Duffel (the flights API, test mode)"
if quiet auth status | grep -qi '^duffel '; then
  echo "Already connected."
else
  echo "Get a free test key in 2 minutes:"
  echo "  1. Sign up at https://app.duffel.com/join (test mode is on by default)"
  echo "  2. Developers > Access tokens > Create token, and copy it (starts with duffel_test_)"
  echo "Paste it below. It's hidden, stays on this machine, and never goes into a chat."
  swy auth connect Duffel
fi

bold "4/6  Connect Google Sheets"
if quiet auth status | grep -qi 'google'; then
  echo "Already connected."
else
  echo "Open the link and sign in with the Google account your assistant (Instinct) uses."
  echo "The bridge makes one sheet called Trips there, and its rules stop it touching any other sheet."
  swy auth connect "Google Sheets"
fi

bold "5/6  Connect Resend (booking confirmation emails)"
if quiet auth status | grep -qi '^resend '; then
  echo "Already connected."
else
  echo "Get a free API key at https://resend.com/api-keys (Sending access is enough)."
  echo "Until you verify a domain, Resend only delivers to the email you signed up with,"
  echo "so use that address as the traveller's email. Paste the key below (hidden)."
  swy auth connect Resend
fi

bold "6/6  Where should approvals go?"
echo "Bookings over $100 wait for your OK. In https://app.swytchcode.com go to"
echo "Settings > Workspaces > book-my-trip > HITL Notifications, and pick Telegram or Slack."
read -r -p "Which did you pick? [telegram/slack] " app
case "$(printf %s "$app" | tr "[:upper:]" "[:lower:]")" in
  t*) app=Telegram ;;
  *)  app=Slack ;;
esac
# Times in the sheet should be in this machine's time zone, not the container's UTC.
tz=$(readlink /etc/localtime 2>/dev/null | sed 's#.*/zoneinfo/##')
[ -z "$tz" ] && tz=$(cat /etc/timezone 2>/dev/null || echo UTC)
grep -v -e '^APPROVAL_APP=' -e '^TZ=' .env 2>/dev/null > .env.tmp || true
printf 'APPROVAL_APP=%s\nTZ=%s\n' "$app" "$tz" >> .env.tmp && mv .env.tmp .env

bold "Starting the bridge"
docker compose up -d
for _ in $(seq 1 60); do
  url=$(docker compose logs bridge 2>/dev/null | grep -o 'https://docs.google.com/spreadsheets/[^ ]*' | tail -1 || true)
  [ -n "$url" ] && break
  sleep 2
done
if [ -z "${url:-}" ]; then
  echo "The bridge didn't start cleanly. See: docker compose logs bridge"
  exit 1
fi

bold "Done. Your Trips sheet: $url"
cat <<EOF

Now send this to Instinct on WhatsApp. The link matters: it stops Instinct using an older
sheet with the same name.

  "Use only this Google Sheet: $url
   Read its 'How to use' tab and follow it. When I ask for flights, add a row to the
   Requests tab, wait 15 seconds, then read me the result."

Then try: "Find me a flight from London to New York on 2026-12-18 under \$500", then "Book option 1".
Instinct asks for your traveller details before the first booking. Give the email you signed
up to Resend with, or the confirmation email can't be delivered.

Approvals arrive in $app. Logs: docker compose logs -f bridge
EOF
