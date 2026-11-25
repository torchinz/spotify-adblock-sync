# spotify-adblock-sync

Two auto-updating blocklists, refreshed every night:

| List | Little Snitch URL | NextDNS |
|---|---|---|
| Spotify ads & trackers | `https://raw.githubusercontent.com/torchinz/spotify-adblock-sync/main/dist/spotify-ads.txt` | pushed to Denylist |
| Every uBlock Origin filter list (network-level rules, ~167k domains) | `https://raw.githubusercontent.com/torchinz/spotify-adblock-sync/main/dist/ubo-all.txt` | uBO's own lists (~3.5k) pushed to Denylist; EasyList, EasyPrivacy, AdGuard etc. are built-in NextDNS lists |

How the uBlock list is built: `scripts/build_ubo.py` reads uBO's catalogue, downloads all its
filter lists (except Unbreak, LAN-block, URL-tracking and Experimental), keeps only rules that
block a whole domain, applies uBO's own `@@` exceptions, and never blocks anything in
`config/never-block.txt` (Apple, Google, Microsoft, WhatsApp, banks' parent domains, social apps,
Spotify, GitHub, NextDNS). Per-list counts: `dist/ubo-stats.txt`.

The Spotify list works like this:

```
 upstream Spotify lists ──► GitHub Action (daily) ──► dist/spotify-ads.txt ──► Little Snitch (Mac)
        + config/allow.txt         │
        + config/deny-extra.txt    └──► NextDNS Denylist ──► iPhone, Mac, router, anything on your profile
```

* **Stays current.** The list rebuilds every night at 03:07 IST and whenever you edit `config/`.
  Little Snitch and NextDNS pick up the changes on their own.
* **Doesn't break playback.** Hosts Spotify needs to connect, log in or stream are never blocked
  (`scripts/build.py` rules + `config/allow.txt`).
* **Leaves your own NextDNS entries alone.** They're recorded in `state/nextdns-yours.txt` and
  always kept, as is anything you add by hand later. The sync updates the Denylist in one bulk
  request. It stops if it would remove more than half of its own entries, if the Spotify list
  is empty, or if the Denylist would go over NextDNS's 5,000-entry cap.

## One-time setup (about 10 minutes)

### 1. Put this folder on GitHub
1. github.com ▸ **New repository** ▸ name it `spotify-adblock-sync`. Make it **Public** if you want
   Little Snitch to subscribe to the list (the list holds only ad domains, never your key).
2. Upload everything in this folder, including the hidden `.github` folder. In Terminal:
   ```
   cd spotify-adblock-sync
   git init -b main && git add . && git commit -m "init"
   git remote add origin https://github.com/<YOU>/spotify-adblock-sync.git
   git push -u origin main
   ```

### 2. Connect NextDNS
1. Copy your API key from the bottom of https://my.nextdns.io/account, and your
   6-character profile ID from the **Setup** tab.
2. In the repo: **Settings ▸ Secrets and variables ▸ Actions ▸ New repository secret**
   * `NEXTDNS_API_KEY`, your key
   * `NEXTDNS_PROFILE`, your profile ID
3. **Actions ▸ Update Spotify blocklist ▸ Run workflow.** The log should end with
   `added ~40 | removed 0 | failed 0`. In NextDNS, open **Denylist**: the Spotify entries are there.

### 3. Mac (Little Snitch 6)
See [`mac/little-snitch-blocklists.md`](mac/little-snitch-blocklists.md). In short:
**Blocklists ▸ +** ▸ `https://raw.githubusercontent.com/<YOU>/spotify-adblock-sync/main/dist/spotify-ads.txt`
▸ update daily. Then remove the static `.lsrules` files you imported earlier.

### 4. iPhone
1. On the iPhone, open **https://apple.nextdns.io** in Safari, enter your profile ID, set a
   device name (e.g. "Chinmay iPhone") and download the profile.
2. **Settings ▸ Profile Downloaded ▸ Install.** This makes iOS use NextDNS on Wi-Fi and mobile data.
   If you also have the NextDNS app, keep only one of the two.
3. **iCloud Private Relay:** when it's on, Safari skips NextDNS. Apps like Spotify still
   use it. Turn Relay off (Settings ▸ [your name] ▸ iCloud ▸ Private Relay) if you want Safari
   filtered too.
4. Spotify ▸ Settings ▸ Storage ▸ **Clear cache**, then force-quit and reopen.
5. Check: NextDNS ▸ **Logs** ▸ filter by the iPhone. Play a few tracks and look for blocked
   `adeventtracker.spotify.com` / `ads-*.spotify.com` entries.

## Everyday use
| You want to… | Do this |
|---|---|
| Unblock a site the uBlock list broke | Add its domain to `config/never-block.txt`, commit. |
| Fix Spotify not connecting or playing | Find the blocked host (NextDNS Logs or Little Snitch), add it to `config/allow.txt`, commit. It's unblocked everywhere within a minute. |
| Block another host | Add it to `config/deny-extra.txt`, commit. |
| Add another upstream list | Add its URL to `config/sources.txt`. |
| Preview without changing NextDNS | Run locally with `DRY_RUN=1 NEXTDNS_API_KEY=… NEXTDNS_PROFILE=… python3 scripts/sync_nextdns.py` |
| Remove everything this added | Delete the domains in `state/nextdns-managed.txt` from your NextDNS Denylist and remove the Little Snitch subscription. |

GitHub pauses scheduled workflows in a public repo after 60 days with no commits. You'll
get an email first. Re-enable it under **Actions**, or commit any small change.

## What this can't do
DNS blocking stops Spotify's ad-serving, tracking and video-ad hosts. It can't remove
audio ads delivered through the same servers as the music, because blocking those stops
the music too. Spotify Premium is the only reliable way to remove those.

## Credits
Upstream Spotify list: [x0uid/SpotifyAdBlock](https://github.com/x0uid/SpotifyAdBlock) (MIT).
