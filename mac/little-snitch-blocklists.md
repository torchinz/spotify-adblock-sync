# Little Snitch 6 — subscribe instead of importing static files

Little Snitch 6 downloads blocklists by URL (hosts files, plain domain lists, .lsrules)
and refreshes them on a schedule. Use these subscriptions instead of the static
`NextDNS-Ads-Trackers.lsrules` / `Spotify-Ads.lsrules` files from earlier, and delete those.

**Little Snitch ▸ Blocklists ▸ + ▸ paste URL**, then set updates to **daily**.
After adding each one, check the entry count it shows. A count of 0 means it
couldn't read that format, so remove it.

## 1. Spotify (from this repo)
    https://raw.githubusercontent.com/<YOUR-GITHUB-USER>/spotify-adblock-sync/main/dist/spotify-ads.txt
(The repo must be public for this link to work. If you keep it private, skip this:
the NextDNS sync already covers the Mac when it uses NextDNS.)

## 2. Lists from your NextDNS profile
If the Mac already resolves through NextDNS, these duplicate it. They matter only
for traffic that skips DNS, or for when you turn NextDNS off. A lean choice is
OISD plus one of the others.

| List | URL |
|---|---|
| OISD (big, domains) | https://big.oisd.nl/domainswild |
| StevenBlack | https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts |
| 1Hosts Lite | https://raw.githubusercontent.com/badmojr/1Hosts/master/Lite/domains.txt |
| AdAway | https://raw.githubusercontent.com/AdAway/adaway.github.io/master/hosts.txt |
| Anudeep | https://raw.githubusercontent.com/anudeepND/blacklist/master/adservers.txt |
| GoodbyeAds | https://raw.githubusercontent.com/jerryn70/GoodbyeAds/master/Hosts/GoodbyeAds.txt |
| Peter Lowe | https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext |
| Dan Pollock | https://someonewhocares.org/hosts/hosts |
| Perflyst Smart-TV | https://raw.githubusercontent.com/Perflyst/PiHoleBlocklist/master/SmartTV.txt |
| AdGuard DNS filter | https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt (adblock syntax: check the count) |

EasyList, EasyPrivacy and the AdGuard Base/Tracking filters are mostly page-element
and URL rules, not domains, so they don't suit a network firewall. Leave them on
NextDNS only.

## Allow rules
If something breaks, select the blocked connection in Little Snitch's network
monitor and allow it. For Spotify, it's better to add the host to
`config/allow.txt` in the repo, so the same fix also reaches NextDNS and your iPhone.
