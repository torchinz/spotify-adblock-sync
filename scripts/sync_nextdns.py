#!/usr/bin/env python3
"""Sync dist/nextdns-*.txt into a NextDNS profile's Denylist (one PUT per run).

dist/nextdns-denylist.txt (Spotify) always goes in first; dist/nextdns-ubo.txt fills
the remaining room under NextDNS's 5,000-entry cap.

Your own entries are recorded in state/nextdns-yours.txt on the first run and are always
kept, as is anything you add by hand later. Only the script's own entries change.

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
PRIORITY = ROOT / "dist" / "nextdns-denylist.txt"
EXTRA = ROOT / "dist" / "nextdns-ubo.txt"
STATE = ROOT / "state" / "nextdns-managed.txt"
YOURS = ROOT / "state" / "nextdns-yours.txt"
BASE = os.environ.get("NEXTDNS_API_BASE", "https://api.nextdns.io").rstrip("/")
KEY = os.environ.get("NEXTDNS_API_KEY", "")
PROFILE = os.environ.get("NEXTDNS_PROFILE", "")
DRY = os.environ.get("DRY_RUN") == "1"
NEXTDNS_LIMIT = 5000          # NextDNS caps a Denylist at 5,000 entries
SAFETY_MARGIN = 100           # keep a few slots free for entries you add by hand
MAX_REMOVAL_SHARE = 0.5       # refuse to remove more than half of our own entries in one run


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
            with urllib.request.urlopen(req, timeout=120) as r:
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
    priority = lines(PRIORITY)
    if not priority:
        sys.exit("ERROR Spotify list is empty -- refusing to sync")
    extra = lines(EXTRA)
    managed = lines(STATE)
    entries = call("GET", "/denylist").get("data", [])
    current = {e["id"] for e in entries}
    active = {e["id"]: e.get("active", True) for e in entries}

    # Your own entries: recorded once, then never touched.
    if YOURS.exists():
        yours = lines(YOURS)
    else:
        yours = current - managed - priority - extra
        YOURS.write_text("# Your own NextDNS Denylist entries at setup -- never modified by the sync\n"
                         + "\n".join(sorted(yours)) + "\n")
    yours |= current - managed - priority - extra   # anything you add later by hand

    room = NEXTDNS_LIMIT - len(yours) - SAFETY_MARGIN
    desired = set(priority)
    for d in sorted(extra):
        if len(desired) >= room:
            print(f"note: NextDNS cap reached; {len(extra - desired)} uBO domains go to Little Snitch only")
            break
        desired.add(d)
    desired -= yours

    ours_now = (current - yours)            # includes entries an interrupted run added
    to_add = sorted(desired - current)
    to_remove = sorted(ours_now - desired)
    print(f"profile {PROFILE}: denylist has {len(current)} (yours {len(yours)}) | desired {len(desired)} | "
          f"add {len(to_add)} | remove {len(to_remove)}", flush=True)
    if ours_now and len(to_remove) > MAX_REMOVAL_SHARE * max(len(ours_now), 1) and len(to_remove) > 50:
        sys.exit(f"ERROR would remove {len(to_remove)} of {len(ours_now)} entries -- check upstream; nothing changed")
    if len(yours) + len(desired) > NEXTDNS_LIMIT:
        sys.exit("ERROR would exceed NextDNS's 5,000-entry limit -- nothing changed")
    if DRY:
        for d in to_add[:20]:
            print("  + " + d)
        for d in to_remove[:20]:
            print("  - " + d)
        return

    if to_add or to_remove:
        final = sorted(yours | desired)
        body = [{"id": d, "active": active.get(d, True)} for d in final]
        call("PUT", "/denylist", body)       # one request replaces the whole list
        after = {e["id"] for e in call("GET", "/denylist").get("data", [])}
        missing_yours = yours - after
        if missing_yours:
            # Should never happen; put them straight back.
            for d in sorted(missing_yours):
                call("POST", "/denylist", {"id": d, "active": active.get(d, True)})
            sys.exit(f"ERROR {len(missing_yours)} of your entries went missing and were restored")
        rejected = set(final) - after
        print(f"denylist now {len(after)} | added {len(set(to_add) - rejected)} | removed {len(to_remove)} | "
              f"rejected by NextDNS {len(rejected)}", flush=True)
        for d in sorted(rejected)[:10]:
            print("  ! rejected " + d)
        new_managed = (after - yours)
    else:
        print("no changes")
        new_managed = desired & current
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text("# Denylist entries managed by sync_nextdns.py (do not edit)\n" + "\n".join(sorted(new_managed)) + "\n")


if __name__ == "__main__":
    main()
