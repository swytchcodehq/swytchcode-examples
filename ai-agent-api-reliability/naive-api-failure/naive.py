"""The 'works in testing' version — for the video's PROBLEM half.

This is written the way the tutorials do it: token pasted in the code,
no status check, no log. Run it to film the failure.
"""

import json
import urllib.request

# The key, pasted straight into the code — like every tutorial.
# (In the video story: this is the key that "aged out" three weeks after launch.)
GITHUB_TOKEN = "ghp_thisTokenExpiredWeeksAgo0000000000"

def star_repo(owner, repo):
    req = urllib.request.Request(
        f"https://api.github.com/user/starred/{owner}/{repo}",
        method="PUT",
        headers={"Authorization": f"token {GITHUB_TOKEN}"},
    )
    try:
        urllib.request.urlopen(req)
    except Exception:
        pass  # <-- the silent part: errors vanish here

star_repo("octocat", "Hello-World")
print("⭐ Done! Starred octocat/Hello-World")   # printed no matter what  %