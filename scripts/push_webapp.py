#!/usr/bin/env python3
"""Push a zundamon phrase slug via the Apps Script Web App (no connector CLI needed).

Usage: ZUNDAMON_WEBAPP_URL=<your web app url> python3 push_webapp.py <slug>
Setup: paste scripts/apps_script.gs into your state spreadsheet's Apps Script
project and deploy it as a Web App (see INSTALL.md). seq is assigned by the
script on the spreadsheet side, so this client never rewound the counter.
"""
import json, os, sys, urllib.request

def main() -> int:
    url = os.environ.get("ZUNDAMON_WEBAPP_URL")
    if not url:
        print("set ZUNDAMON_WEBAPP_URL", file=sys.stderr); return 2
    if len(sys.argv) != 2:
        print("usage: push_webapp.py <slug>", file=sys.stderr); return 2
    req = urllib.request.Request(
        url,
        data=json.dumps({"slug": sys.argv[1]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.read().decode())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
