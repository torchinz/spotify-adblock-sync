#!/usr/bin/env python3
"""Sync dist/nextdns-denylist.txt into a NextDNS profile's Denylist.

Only touches entries this script added itself (tracked in state/nextdns-managed.txt).
Domains you added by hand are never removed, even if they are also on the list.

Env:
  NEXTDNS_API_KEY   from https://my.nextdns.io/account (bottom of page)
  NEXTDNS_PROFILE   6-character profile ID
  NEXTDNS_API_BASE  optional, for testing (default https://api.nextdns.io)
  DRY_RUN=1         print the plan without changing anything
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIST = ROOT / "dist" / "nextdns-denylist.txt"
STATE = ROOT / "state" / "nextdns-managed.txt"
BASE = os.environ.get("NEXTDNS_API_BASE", "https://api.nextdns.io").rstrip("/")
KEY = os.environ.get("NEXTDNS_API_KEY", "")
PROFILE = os.environ.get("NEXTDNS_PROFILE", "")
DRY = os.environ.get("DRY_RUN") == "1"
NEXTDNS_LIMIT = 5000          # NextDNS caps a Denylist at 5,000 entries
MAX_REMOVALS_PER_RUN = 200    # guard against a broken upstream wiping the list


def lines(path):
    if not path.exists():
        return set()
    return {l.strip() for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")}


def call(method, path, body=None):
    url = f"{BASE}/profiles/{PROFILE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(5):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "X-Api-Key": KEY, "Content-Type": "application/json", "User-Agent": "spotify-adblock-sync"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                txt = r.read().decode() or "{}"
                return json.loads(txt)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {e.read()[:300]!r}") from None


def main():
    if not KEY or not PROFILE:
        print("NEXTDNS_API_KEY / NEXTDNS_PROFILE not set -- skipping NextDNS sync.")
        return
    desired = lines(LIST)
    if not desired:
        sys.exit("ERROR desired list is empty -- refusing to sync")
    managed = lines(STATE)

    current = {e["id"] for e in call("GET", "/denylist").get("data", [])}
    to_add = sorted(desired - current)
    to_remove = sorted((managed - desired) & current)

    print(f"profile {PROFILE}: denylist has {len(current)} | desired {len(desired)} | "
          f"managed {len(managed)} | add {len(to_add)} | remove {len(to_remove)}")
    if len(to_remove) > MAX_REMOVALS_PER_RUN:
        sys.exit(f"ERROR would remove {len(to_remove)} entries (> {MAX_REMOVALS_PER_RUN}) -- check upstream; nothing changed")
    if len(current) - len(to_remove) + len(to_add) > NEXTDNS_LIMIT:
        sys.exit(f"ERROR would exceed NextDNS's {NEXTDNS_LIMIT}-entry Denylist limit -- nothing changed")
    if DRY:
        for d in to_add[:20]:
            print("  + " + d)
        for d in to_remove[:20]:
            print("  - " + d)
        return

    added, removed, failed = set(), set(), []
    for d in to_add:
        try:
            res = call("POST", "/denylist", {"id": d, "active": True})
            if res.get("errors"):
                failed.append((d, res["errors"]))
            else:
                added.add(d)
        except RuntimeError as e:
            failed.append((d, str(e)))
        time.sleep(0.15)
    for d in to_remove:
        try:
            call("DELETE", "/denylist/" + urllib.parse.quote(d, safe=""))
            removed.add(d)
        except RuntimeError as e:
            failed.append((d, str(e)))
        time.sleep(0.15)

    # Entries we added stay "managed"; entries that already existed (yours) never become managed.
    new_managed = ((managed & current) | added) - removed
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text("# Denylist entries added by sync_nextdns.py (do not edit)\n" + "\n".join(sorted(new_managed)) + "\n")
    print(f"added {len(added)} | removed {len(removed)} | failed {len(failed)}")
    for d, err in failed[:10]:
        print(f"  ! {d}: {err}")
    if failed and not added and not removed:
        sys.exit(1)


if __name__ == "__main__":
    main()
