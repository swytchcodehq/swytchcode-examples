"""Every API call the bridge makes goes through here, to Swytchcode.

Swytchcode holds the keys and checks each call against policies.json. A call
ends one of four ways: it worked (run() returns the API's response), a policy
refused it (Blocked), it's waiting for a person to approve it (NeedsApproval),
or something else went wrong (Failed). Uncertain is a Failed where the call
may still have gone through, so it mustn't simply be tried again.
"""

import datetime as dt
import json
import os
import re
import subprocess

from swytchcode_runtime import exec as swytchcode_exec
from swytchcode_runtime.errors import SwytchcodeError

PROJECT_DIR = os.path.expanduser(os.environ.get("SWYTCHCODE_PROJECT", ".."))

EXIT_BLOCKED = 6  # a policy refused the call
EXIT_APPROVAL_PENDING = 7  # waiting for a person; Swytchcode replays the call once approved
# The request may have reached the API: the CLI's SDK failure and internal error.
EXIT_UNSURE = (4, 5)


class Blocked(Exception):
    """A policy refused the call. The message is the policy's own."""


class NeedsApproval(Exception):
    """The call is waiting for approval. delivered is False when Swytchcode
    couldn't pass the request on to Slack or Telegram yet (it keeps trying)."""

    def __init__(self, delivered):
        super().__init__("waiting for approval")
        self.delivered = delivered


class Failed(Exception):
    """Anything else: a bad response, a network error, a refused approval request."""


class Uncertain(Failed):
    """The call may have gone through: it timed out, or the reply was lost or
    unreadable. Look the result up in the API before trying again."""


def log(msg):
    print(f"{dt.datetime.now():%H:%M:%S}  {msg}", flush=True)


def run(tool, args, env=None, quiet=False):
    """Runs one tool through Swytchcode and returns the API's response body."""
    if not quiet:
        log(f"  swytchcode exec {tool}")
    try:
        result = swytchcode_exec(tool, args, cwd=PROJECT_DIR, timeout=90, env=env)
    except SwytchcodeError as e:
        raise _outcome(e, quiet) from e
    if not isinstance(result, dict):
        raise Uncertain("the API sent back an empty response")
    body = result.get("data", result) if "status_code" in result else result
    status = int(result.get("status_code") or 0)
    if status >= 500:
        raise Uncertain(f"{api_error(body)} (HTTP {status})")
    if status >= 400:
        raise Failed(f"{api_error(body)} (HTTP {status})")
    if not quiet:
        log("  -> ok")
    return body


def _outcome(e, quiet):
    """The exception for a failed `swytchcode exec`, logging what happened."""
    text = e.message or ""
    if e.cause == EXIT_APPROVAL_PENDING:
        undelivered = re.search(r"did not confirm the request yet \((.*?)\)", text)
        if undelivered:
            log(f"  !! approval request not delivered yet: {undelivered.group(1)}")
        else:
            log("  -> waiting for approval")
        return NeedsApproval(delivered=not undelivered)
    reason = cli_error(text)
    # Exit 6 also covers the backend refusing the approval request itself.
    if e.cause == EXIT_BLOCKED and "approval request refused" not in text:
        reason = policy_message(reason)
        log(f"  -> blocked by policy: {reason}")
        return Blocked(reason)
    unsure = (isinstance(e.cause, subprocess.TimeoutExpired) or e.cause in EXIT_UNSURE
              or text.startswith("Invalid JSON output"))
    if not quiet:
        log(f"  -> {'unsure' if unsure else 'failed'}: {reason}")
    return Uncertain(reason) if unsure else Failed(reason)


def policy_message(error):
    """Just the policy's message. The CLI writes
    'blocked by policy "<id>": <message> - <advice for agents>'."""
    error = error.split(" - ", 1)[0]
    match = re.match(r'blocked by policy "[^"]+": (.*)', error, re.S)
    return match.group(1) if match else error


def cli_error(text):
    """The CLI's own error, from the warnings and logs around it."""
    for line in reversed(text.splitlines()):
        if line.startswith("{") and '"error"' in line:
            try:
                return json.loads(line)["error"]
            except (ValueError, KeyError):
                pass
    lines = text.strip().splitlines()
    if not lines:
        return "unknown error"
    # A log line: "2026/10/23 07:39:06 [swytchcode exec] failed tool=... error=<reason>"
    match = re.search(r"\berror=(.*)$", lines[-1])
    return match.group(1) if match else lines[-1]


def api_error(body):
    """The readable part of an API's error response (Duffel, Google or Resend)."""
    if isinstance(body, dict):
        errors = body.get("errors")
        if errors and isinstance(errors[0], dict):
            return errors[0].get("message") or errors[0].get("title") or str(errors[0])
        error = body.get("error")
        if isinstance(error, dict):
            return error.get("message") or str(error)
        if body.get("message"):
            return body["message"]
    return str(body)[:200]
