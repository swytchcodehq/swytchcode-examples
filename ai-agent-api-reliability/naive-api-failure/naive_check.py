"""Same call as naive.py, but this time we actually LOOK at GitHub's answer."""

import urllib.request, urllib.error

GITHUB_TOKEN = "ghp_thisTokenExpiredWeeksAgo0000000000"

req = urllib.request.Request(
    "https://api.github.com/user/starred/octocat/Hello-World",
    method="PUT",
    headers={"Authorization": f"token {GITHUB_TOKEN}"},
)
try:
    resp = urllib.request.urlopen(req)
    print("GitHub said:", resp.status)
except urllib.error.HTTPError as e:
    print("GitHub said:", e.code, e.reason)
    print(e.read().decode())
