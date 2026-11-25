#!/usr/bin/env python3
"""Build one domain blocklist from every filter list uBlock Origin ships.

Reads uBO's own catalogue (assets/assets.json in gorhill/uBlock), downloads each list,
and keeps only rules that work at the network/DNS level:
    ||example.com^            (no options, or only $third-party / $important / $all / $doc / $popup)
    0.0.0.0 example.com       (hosts format)
    example.com               (plain domain lists)
Cosmetic rules (##), URL-path rules, type-limited rules ($script, $image...) and scriptlets
are skipped: they target part of a site, and blocking the whole domain would break it.
config/never-block.txt protects the big platforms your devices rely on.
@@ exception rules and config/allow.txt remove domains from the result.

Outputs:
  dist/ubo-all.txt          everything, for Little Snitch
  dist/ubo-stats.txt        per-list counts and fetch failures
  dist/nextdns-ubo.txt      domains from uBO's OWN lists (the part NextDNS has no built-in list for)
"""
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG, DIST = ROOT / "config", ROOT / "dist"
CATALOGUE = "https://raw.githubusercontent.com/gorhill/uBlock/master/assets/assets.json"

# Lists that must not be turned into a network blocklist.
EXCLUDE = {
    "ublock-unbreak": "allow rules only",
    "block-lan": "would block your own router, printer and other LAN devices",
    "adguard-spyware-url": "strips URL parameters; contains no domains",
    "ublock-experimental": "uBO's own staging list; known to break sites",
}
MIN_LISTS_OK = 0.75        # abort if fewer than 75% of lists download
MIN_DOMAINS = 50_000       # abort if the result is implausibly small

DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z]{2,63}$")
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
NET_RULE = re.compile(r"^(@@)?\|\|([a-z0-9._-]+)\^\|?(?:\$(.*))?$")
OK_OPTS = {"important", "all", "doc", "document", "popup", "third-party", "3p", ""}
UBO_OWN = {"ublock-filters", "ublock-privacy", "ublock-badware", "ublock-quick-fixes",
            "ublock-annoyances", "ublock-cookies-adguard", "ublock-cookies-easylist"}
NEXTDNS_ROOM = 4500  # NextDNS Denylist caps at 5,000; leave room for Spotify + your own entries
COSMETIC = ("##", "#@#", "#?#", "#$#", "#%#", "#+js")


def fetch(urls):
    last = "no http URL"
    for url in urls:
        if not url or not url.startswith("http"):
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 spotify-adblock-sync"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return url, r.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            last = f"{url}: {e}"
    raise RuntimeError(last)


def parse(text):
    block, allow = set(), set()
    for line in text.splitlines():
        line = line.strip().lower()
        if not line or line[0] in "![" or any(c in line for c in COSMETIC):
            continue
        if line.startswith("#"):
            continue
        m = NET_RULE.match(line)
        if m:
            exc, dom, opts = m.groups()
            opts = {o.strip() for o in (opts or "").split(",")}
            if not opts <= OK_OPTS or not DOMAIN_RE.match(dom):
                continue
            (allow if exc else block).add(dom)
            continue
        parts = line.split("#")[0].split()
        if len(parts) == 2 and IP_RE.match(parts[0]) and DOMAIN_RE.match(parts[1]):
            block.add(parts[1])
        elif len(parts) == 1 and DOMAIN_RE.match(parts[0]):
            block.add(parts[0])
    return block, allow


def under(d, parents):
    p = d.split(".")
    return any(".".join(p[i:]) in parents for i in range(len(p) - 1))


def collapse(domains):
    s = set(domains)
    return sorted(d for d in s if not any(".".join(d.split(".")[i:]) in s for i in range(1, len(d.split(".")) - 1)))


def cfg(name):
    out = set()
    for line in (CFG / name).read_text().splitlines():
        line = line.split("#")[0].strip().lower().strip(".")
        if line:
            out.add(line)
    return out


def main():
    url, raw = fetch([CATALOGUE])
    assets = {k: v for k, v in json.loads(raw).items() if v.get("content") == "filters"}
    block, allow, own, stats, failed = set(), set(), set(), [], []
    for key, a in sorted(assets.items()):
        if key in EXCLUDE:
            stats.append(f"SKIP  {key:28s} {EXCLUDE[key]}")
            continue
        urls = a.get("contentURL", [])
        urls = (urls if isinstance(urls, list) else [urls]) + (a.get("cdnURLs") or [])
        try:
            src, text = fetch(urls)
        except RuntimeError as e:
            failed.append(key)
            stats.append(f"FAIL  {key:28s} {e}")
            continue
        b, al = parse(text)
        block |= b
        allow |= al
        if key in UBO_OWN:
            own |= b
        stats.append(f"{len(b):7d} {key:28s} {a.get('title', '')}")
    tried = len(assets) - len(EXCLUDE)
    print("\n".join(stats))
    if tried and (tried - len(failed)) / tried < MIN_LISTS_OK:
        sys.exit(f"ERROR only {tried - len(failed)}/{tried} lists downloaded -- dist/ubo-all.txt left unchanged")

    never = cfg("allow.txt") | cfg("never-block.txt")
    result = collapse(d for d in block if not under(d, allow) and not under(d, never))
    if len(result) < MIN_DOMAINS:
        sys.exit(f"ERROR only {len(result)} domains -- dist/ubo-all.txt left unchanged")

    own_final = [d for d in collapse(d for d in own if not under(d, allow) and not under(d, never))]
    if len(own_final) > NEXTDNS_ROOM:
        print(f"WARNING uBO-own list has {len(own_final)} domains; keeping {NEXTDNS_ROOM} for NextDNS")
        own_final = own_final[:NEXTDNS_ROOM]

    DIST.mkdir(exist_ok=True)
    (DIST / "nextdns-ubo.txt").write_text(
        "# Domains from uBlock Origin's own filter lists, pushed to the NextDNS Denylist (auto-generated)\n"
        + "\n".join(own_final) + "\n")
    (DIST / "ubo-all.txt").write_text(
        "# Every network-level rule from the filter lists uBlock Origin ships (auto-generated)\n"
        "# Excluded lists and per-list counts: dist/ubo-stats.txt\n" + "\n".join(result) + "\n")
    (DIST / "ubo-stats.txt").write_text(
        "\n".join(stats) + f"\n\nlists used {tried - len(failed)}/{tried} | raw {len(block)} | "
        f"exceptions {len(allow)} | final (subdomains collapsed) {len(result)} | NextDNS part {len(own_final)}\n")
    print(f"lists {tried - len(failed)}/{tried} | raw {len(block)} | exceptions {len(allow)} | "
          f"final {len(result)} | NextDNS part {len(own_final)}")


if __name__ == "__main__":
    main()
