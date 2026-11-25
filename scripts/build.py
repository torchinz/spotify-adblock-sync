#!/usr/bin/env python3
"""Build the Spotify ad blocklist from upstream sources plus local config.

Outputs (in dist/):
  spotify-ads.txt         plain domain list  -> Little Snitch 6 blocklist subscription
  spotify-ads.lsrules     rule group JSON    -> Little Snitch 4.2+/5 subscription or import
  nextdns-denylist.txt    Spotify-only subset -> pushed to NextDNS by sync_nextdns.py

Safety rules:
  * Hosts Spotify needs to connect, log in or stream are never blocked (CORE_HINT + allow.txt).
  * On Spotify's own domains, only hosts that look like ads/tracking are kept (AD_HINT).
  * If any source fails, or the result looks implausibly small, nothing is written.
"""
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG, DIST = ROOT / "config", ROOT / "dist"

DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z]{2,63}$")
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
SPOTIFY_RELATED = re.compile(r"spotify|(^|\.)(p?scdn\.co|scdn\.com|spotimg\.com)$")
AD_HINT = re.compile(
    r"(^|[.-])(ads?|ad-proxy|adstudio|adeventtracker|adsvc|analytics|crashdump|pixel|surveys?|"
    r"upsell|upgrade|tracker|telemetry|beacon|logs?|metrics|video-ak|video-fa|video-akp)([.-]|\d|$)"
)
CORE_HINT = re.compile(
    r"accesspoint|weblb|apresolve|spclient|dealer|login5|msproxy|audio-sp|audio-fa|audio-ak|audio4|"
    r"audio-gc|api|accounts?|open|play|image|mosaic|seed|heads|gew|guc|gae"
)
NOISE = re.compile(r"\.bc\.googleusercontent\.com$")  # GCP reverse-DNS names nobody resolves
MIN_SPOTIFY_ENTRIES = 20


def read_cfg(name, lower=True):
    out = []
    for line in (CFG / name).read_text().splitlines():
        line = line.split("#")[0].strip()
        if lower:
            line = line.lower().strip(".")
        if line:
            out.append(line)
    return out


def parse(text):
    found = set()
    for line in text.splitlines():
        line = line.split("#")[0].strip().lower()
        if not line or line.startswith("!"):
            continue
        if line.startswith("||"):  # adblock syntax ||domain^
            line = line[2:].split("^")[0]
        parts = line.split()
        d = parts[1] if len(parts) >= 2 and IP_RE.match(parts[0]) else parts[0]
        d = d.strip(".")
        if not IP_RE.match(d) and DOMAIN_RE.match(d):
            found.add(d)
    return found


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "spotify-adblock-sync"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def under(d, parents):
    """True if d equals or is a subdomain of anything in parents."""
    p = d.split(".")
    return any(".".join(p[i:]) in parents for i in range(len(p) - 1))


def collapse(domains):
    """Drop entries already covered by a blocked parent (both LS and NextDNS match subdomains)."""
    s = set(domains)
    return sorted(d for d in s if not any(".".join(d.split(".")[i:]) in s for i in range(1, len(d.split(".")) - 1)))


def main():
    raw = set()
    for url in read_cfg("sources.txt", lower=False):
        try:
            got = parse(fetch(url))
        except Exception as e:  # noqa: BLE001
            sys.exit(f"ERROR fetching {url}: {e} -- nothing written")
        print(f"{len(got):6d}  {url}")
        raw |= got

    allow = set(read_cfg("allow.txt"))
    extra = set(read_cfg("deny-extra.txt"))

    kept, dropped_core = set(), []
    for d in raw:
        if NOISE.search(d):
            continue
        if SPOTIFY_RELATED.search(d):
            if AD_HINT.search(d) and not CORE_HINT.search(d):
                kept.add(d)
            else:
                dropped_core.append(d)
        else:
            kept.add(d)
    kept |= extra
    kept = {d for d in kept if not under(d, allow)}

    full = collapse(kept)
    spotify_only = [d for d in full if SPOTIFY_RELATED.search(d)]
    if len(spotify_only) < MIN_SPOTIFY_ENTRIES:
        sys.exit(f"ERROR only {len(spotify_only)} Spotify entries (< {MIN_SPOTIFY_ENTRIES}) -- nothing written")

    DIST.mkdir(exist_ok=True)
    header = (
        "# Spotify ads & tracking blocklist (auto-generated, do not edit)\n"
        "# Sources: config/sources.txt  |  Exceptions: config/allow.txt  |  Extras: config/deny-extra.txt\n"
    )
    (DIST / "spotify-ads.txt").write_text(header + "\n".join(full) + "\n")
    (DIST / "nextdns-denylist.txt").write_text(header + "\n".join(spotify_only) + "\n")
    lsrules = {
        "name": "Spotify Ads",
        "description": "Spotify ad/tracker hosts, filtered so playback keeps working. Auto-updated daily.",
        "denied-remote-domains": full,
    }
    (DIST / "spotify-ads.lsrules").write_text(json.dumps(lsrules, indent=1) + "\n")
    print(f"raw {len(raw)} | dropped as core/streaming {len(dropped_core)} | "
          f"full list {len(full)} | NextDNS subset {len(spotify_only)}")


if __name__ == "__main__":
    main()
