# Change Plan

Status: **Draft v2** (23 Nov 2026). Goal: everything built and tested by **31 Dec 2026**, ready for IPL 2027.
Effort: S = under 30 min, M = about 1–2 h, L = half a day or more, XL = 2 days or more.

---

## A. User-requested changes

| # | Change | Section |
|---|--------|---------|
| A1 | Cut the data cost (RapidAPI is about ₹1000 a month) | E |
| A2 | Live player auction: each owner bids from their own phone, on the same Railway app | F, G |

---

## H. Accounts, leagues, social (agreed 24 Nov)
Full proposal: user accounts separate from teams; tournament vs league split (more leagues at no API cost); emails collected with consent (DPDP Act); league-private social feed built from match data plus WhatsApp share cards; Railway is fine for this.
Decisions: SQLite on the volume for now (DATABASE_URL switches to Postgres later); email log-in links later; no custom domain yet (emails are collected but not sent until there is one; adding a domain later takes about 30 minutes and needs no code change); second IPL league timing not decided.
- **H1. Owner accounts + join links:** ✅ Built 24 Nov. /admin/people (create, copy or WhatsApp a link; log-in link for a new phone; release; CSV export), /join/<token>, /account (edit, download, delete), /privacy. Database at data/gullyxi.db, included in /api/export-data.
- H2. My team pages. H3. Tournament/league split. H4. Feed + share cards. H5. Email sending (needs a domain).

## I. Trading window and market (agreed 24 Nov)
Decisions: trades go through instantly, and the admin can reverse within 24 hours. Money is in lakhs and shown in crores. Player prices count against purses, and the admin tops up purses for 2027 (amount to be decided). Trading is between owners only for now; retention and a free pool come later. No limits apart from purses staying at zero or above.
- **I1. Squad history:** ✅ built (squads.py). A match is scored with the squads in force when it started, so a rescore never moves earlier points. Deploys don't overwrite squads once they've been changed on the site.
- **I2. Market stages:** ✅ built. Off, scheduled, live, paused or closed, per tournament (market.json); owners see nothing while it's off.
- **I3. Trading window:** ✅ built. Offers, counter-offers, accept, decline and withdraw; purse checks; auto-cancel of clashing offers; inbox badge and banner; WhatsApp nudge; trade log; admin reverse; captain/vice-captain fallback; no trades during matches; purse top-up.
- Next: create the IPL 2027 tournament (2026 squads carried over), let owners pick their own C/VC, retention/free pool once decided, then the live auction (F).

## E. Data fetching on the free tier (A1)

**Diagnosis:** the cost comes from the number of calls. Each run makes list calls for both leagues, 5 runs a day, so about 300 calls a month before any scorecard. Each new match adds 2 more (`hscard` and `comm` for Man of the Match).
**Target:** about 130 calls a month during IPL. The current listing (`cricbuzz-cricket`) has a free Basic plan of 200 a month.

### E1. Schedule cache — M  ✅ **Done 24 Nov**
- Fetch the season fixture list once, store it in `data/<league>/schedule.json`, and refresh it weekly. The refresh is 1 call.
- On each run, pick only matches where start time + 4 h has passed, the match isn't processed yet, and its schedule entry isn't marked complete. Then fetch only those scorecards.
- If no match is due, the run makes **0 API calls**.
- **Files:** `cricbuzz_api.py`, `main.py` (auto-score), `web/routers/api.py`

### E2. Call budget guard — S  ✅ **Done 24 Nov**
- Count every API call in `data/api_usage.json`, per month and per key.
- Refuse calls above a configurable cap (default 180 a month), and show the usage on the admin page.

### E3. Second free key as overflow — S/M  🟡 **Built 24 Nov, response shape not verified: needs a free key on that listing**
- Test the `cricbuzz-cricket2` listing (free plan, 100 a day). If its `hscard` response has the same shape, use it automatically when key 1 reaches its cap.
- If the shape differs, write a small adapter, or drop this item.

### E4. Manual scorecard upload — M  ✅ **Done 24 Nov (Scoring admin page)**
- Admin page to upload a scorecard JSON for a match ID (or paste one). It is cached and scored exactly like an API result.
- This is the safety net for any match the API misses.

### E5. Retry Man of the Match — S  ✅ **Done 24 Nov**
- The `comm` call is made only when the scorecard has no MoM, and it's retried on the next run if MoM wasn't announced yet.
- Rescoring then adds the +30 once MoM is found.

### E6. Schedule the GitHub Action for match days only — S  ✅ **Cron on 24 Nov (3 runs a day; idle runs cost 0 calls)**
- With E1 in place, the Action can run often; empty runs cost nothing. Change the cron to cover IPL match windows (about 7:30 PM and 11:30 PM IST, plus the afternoon for double-headers) and turn it on only during the season.
- **Action for the user:** check which RapidAPI plan you're on, and move to Basic (free) once E1 and E2 are live.

---

## F. Live auction: owners bid from their own phones (A2)

### F1. Owner accounts — M
- Move users out of hardcoded `config.py` into `data/users.json` on the Railway volume. Roles: `admin`, `owner` (linked to one fantasy team), `viewer`.
- Admin page to create owners, link each to a team name, and reset passwords. Passwords stay bcrypt-hashed.
- Optional: a per-owner join link with a one-time code, so nobody has to type passwords on a phone.

### F2. Auction rules config — S
- `data/<league>/auction_rules.json`. Every rule lives here, so finalising the rules later needs no code change:
  - `budget`, `squad_min`, `squad_max`
  - `role_min` (e.g. WK ≥ 1, BOWL ≥ 4 …), `overseas_max`
  - `base_price` (per player or per set), `bid_increments` (e.g. +25 up to 500, then +50 …)
  - `bid_timer_seconds` (e.g. 15 s, reset on every bid)
  - `max_bid_rule`: purse − (slots left − 1) × base price, so an owner can always complete the minimum squad
  - placeholders for `retentions` and `rtm`, depending on the final rules

### F3. Player pool and sets — M
- `data/<league>/auction_pool.json`: name, role, country, IPL team, base price, **set** (Marquee, Batters, Bowlers …) and order.
- Import from Excel/CSV through an admin upload. For testing, use the 2026 `players_data.json`.

### F4. Auction engine (server side) — L
- One authoritative state: current player, current bid, leading owner, timer end time, status (`waiting / live / paused / sold / unsold`), and each owner's purse and squad.
- **Bids:** `POST /api/auction/bid`, handled under one lock. The server validates each bid:
  - the amount equals current bid + the correct increment
  - the bidder has enough purse under the max-bid rule
  - the squad isn't full and the overseas cap isn't broken
  - the bidder isn't already the leader

  Two bids at the same moment: the first one wins, the second gets "outbid".
- **The timer runs on the server,** not on phones. When it runs out, the player is SOLD to the leader, or UNSOLD if there were no bids.
- **Every event is written to `data/<league>/auction_log.jsonl`.** State is rebuilt from the log after a restart or redeploy, so nothing is lost mid-auction.
- **Admin controls:** next player, pause/resume, sell now, mark unsold, **undo last sale**, re-auction unsold players (round 2), end auction.

### F5. Real-time updates — M
- **Server-Sent Events** (`GET /api/auction/stream`) push every state change to all phones. This is simpler than WebSockets and works through Railway's proxy. Bids go through the normal POST.
- On reconnect, the phone gets the full state again, so a dropped mobile connection recovers by itself.
- Fallback: if SSE is blocked, poll every 2 s.

### F6. Owner bid screen (mobile first) — L
- Shows the current player card (name, role, country, base price, set), the current bid, who is leading, and a countdown.
- **One big "BID ₹X" button** with the next valid amount pre-calculated. It's disabled with a reason when the owner can't bid ("purse", "overseas full", "you're leading").
- Shows my purse, my max bid, my squad by role, and the roles still needed.
- Feedback on every action: "You're leading", "Outbid by Priyanka", "SOLD to you ₹850".

### F7. Admin console and public board — M
- **Admin console:** controls from F4, the upcoming players queue, the live log, and every owner's connection status (online or offline).
- **Board** (for a TV or screen share, and for viewers): all teams with purse left and squad count, the last 10 sales, and the current lot.

### F8. Auction → league setup — S/M
- "Finalise auction" writes `teams_data.json` and `players_data.json` for the new season. Each owner's squad comes with prices and roles; budget = purse.
- Next step: each owner picks **C/VC on their phone** before a deadline, which locks it.
- Download the auction results as Excel: per team, plus the full sale log.

### F9. Test the auction — M
- Script `tools/simulate_auction.py`: 11 fake owners bidding at random over HTTP. It checks for race conditions, budget/overseas rules, undo, and recovery after a restart.
- **Dry run with real people:** a 15-minute mock auction on phones about a week before the real one.

---

## G. Season setup for IPL 2027

### G1. Add a new league config `ipl27` — S/M  ✅ **Done 23 Nov**
- Keep IPL 2026 and WWC 2026 viewable as archives. Add `IPL27_CONFIG` (`data/ipl27/`, `/ipl27`), so the 2027 data never mixes with the 2026 data.
- The home page lists all seasons, current one first.
- Generalise the league-specific bits that still check `== "wwc"` (rescore buttons, rules) so they work through the config. This overlaps with D2.

### G2. Scoring rules for 2027 — S
- Add `IPL27_RULES` to `scoring.py` once the rules are final. Base it on the IPL rules; the `ScoringRules` dataclass already supports variations.
- Rescore a few 2026 matches with the new rules as a test.

### G3. Load the real player pool — S
- After the real IPL 2027 auction (usually mid-December), import the final IPL squads as the pool (F3). Use one API call per team, or a CSV.

---

## B. Bug fixes (wrong behaviour on the live site)

### B1. WWC master sheet "View" link opens the IPL path — S  ✅ **Done 23 Nov**
- **Problem:** in the "Matches Processed" table, the View button points to `/dashboard/match/{id}`, so WWC matches open under IPL and fail.
- **Fix:** use `{{ league.dashboard_prefix }}/match/{id}`.
- **Files:** `web/templates/master.html`

### B2. Hardcoded "IPL" naming on WWC pages and Excel files — S/M  ✅ **Done 23 Nov**
- **Problem:** browser tab titles (master, history, match detail and others) and Excel headings ("IPL Fantasy Premier League 2026") are the same for both leagues.
- **Fix:** templates use `{{ league.name }}`. Excel export functions take the `cfg` they already receive and use `cfg.name` in titles.
- **Files:** `web/templates/*.html`, `leaderboard.py` (master, team points, summary, detailed, teams and analytics exports)

### B3. Teams Excel shows IPL-only columns for WWC — S
- **Problem:** the "Indian / Overseas" counts mean nothing for WWC.
- **Fix:** for WWC, replace them with a per-country count, or drop them.
- **Files:** `leaderboard.py` → `export_teams_to_excel`
- **Decision:** show a country breakdown, or drop the columns?

### B4. Match order differs between pages — S  ✅ **Done 23 Nov**
- **Problem:** History lists newest first, the Master Sheet matches table lists oldest first, and the Excel column order follows the order matches were stored.
- **Fix:** pick one order and use it everywhere. Proposal: the website shows newest first; Excel columns stay oldest to newest, left to right, because that reads naturally as a timeline.
- **Files:** `web/services.py`, `leaderboard.py`
- **Decision:** confirm the proposal.

---

## C. Operations

### C1. Auto-score still runs although both tournaments are over — S  ✅ **Done 23 Nov**
- **Problem:** IPL 2026 and the June–July WWC 2026 have finished. The GitHub Action still runs 5 times a day and calls the RapidAPI quota for nothing.
- **Options:**
  1. Disable the schedule and keep manual "Run workflow" (recommended).
  2. Cut it to one run a day.
  3. Leave it as it is.
- **Files:** `.github/workflows/auto-score.yml`
- **Decision:** which option?

### C2. Backups: real data exists only on the Railway volume — M  ✅ **Done 23 Nov**
- **Problem:** WWC scores, history and master sheet exist only on Railway. The local copy is stale: uncommitted IPL data changes and about 37 untracked scorecards.
- **Fix:**
  1. Take a final snapshot with `/api/export-data` (the zip), or with the existing `python main.py sync-data`.
  2. Choose a policy for data in git: either commit end-of-season snapshots, or git-ignore `data/` and keep zips elsewhere.
  3. Clean the local working tree so it matches that policy.
- **Decision:** should final tournament data be committed to git as an archive?

### C3. Single data source (Cricbuzz on RapidAPI) — L, deferred
- **Problem:** there's no fallback if the key or plan stops working. The ESPN/cricapi work was never finished.
- **Proposal:** park this until there's a next tournament. Revisit then (cricapi needs a free API key from the user).

---

## D. Cleanup / consistency

### D1. Remove the now-unnecessary "Refresh C/VC" — S  ✅ **Done 23 Nov**
- C/VC is now read live from the teams config, so the button and `POST /api/wwc/refresh-captains` are dead weight.
- **Files:** `web/routers/api.py`, `web/templates/history.html`

### D2. Make the admin tools work for both leagues — M  ✅ **Done 23 Nov**
- **Problem:** Rescore and Rescore All exist only for WWC.
- **Fix:** generalise to `POST /api/{league}/rescore/{id}` and `/api/{league}/rescore-all`, and show the buttons on both leagues' History pages. Optionally add a per-match "Rescore" button.
- **Files:** `web/routers/api.py`, `web/templates/history.html`, `main.py` (shared score function)

### D3. CLI breakdown view prints IPL rules for every league — S
- `show_detailed` in `leaderboard.py` hardcodes the 30-run milestone, ×0.5 dot balls and the WK duck rule. Make it read `ScoringRules`.
- CLI only, no effect on the website. Low priority.

### D4. Remove leftover files — S
- Candidates: `_find_ids.py`, `build_players_db.py` (one-off 2026 script; still points at the old root `teams_data.json`), `data/test_*_export.xlsx`, and `DEPLOY_NOW.md` (check whether it's still accurate).
- **Keep** `config_prod.py`: `app.py` loads it for production settings.
- **Decision:** confirm deletions.

---

## Timeline (to 31 Dec 2026)

| Week of | Work | Items |
|---|---|---|
| 23 Nov | Back up the 2026 data, quick wins, stop the wasted API calls | C2, B1, B2, B4, D1, C1 |
| 30 Nov | Free-tier data fetching, plus the new season setup | E1–E5, G1, D2 |
| 7 Dec | Auction backend: users, rules, pool, engine, real-time stream | F1–F5 |
| 14 Dec | Auction phone screen, admin console, board, finalise step | F6–F8 |
| 21 Dec | Simulated auction, mock auction with real people, fixes; load the real pool | F9, G3, B3, D3, D4 |
| 28 Dec | Buffer, final rules, IPL 2027 scoring rules | G2, E6 |

C3 (a second data provider) stays parked; E3 and E4 cover the same risk for now.

## Open decisions
- [ ] **Auction rules** (needed by 7 Dec for F2; placeholders are fine until then): budget, squad min/max, role minimums, overseas cap, base prices and sets, bid increments, timer length, retentions or RTM?
- [ ] **Number of owners for 2027**, and their names (for F1)
- [ ] **Auction date**, so we know the dry-run date
- [ ] F1: plain password per owner, or one-time join links?
- [ ] B3: country breakdown or drop the columns?
- [ ] D4: OK to delete the listed files?

## Decided
- 23 Nov: **WPL 2027** (season 14 Jan – 7 Feb 2027; real auction was 28 Oct) is our next tournament. The WPL auction is done **offline**; the user supplies managers, teams and prices (prices may be 0). The auction feature stays a generic base feature for later (IPL).
- 23 Nov: restructured into tournaments: `data/tournaments/<id>/tournament.json`, URLs `/<competition>/<season>` (old `/dashboard` and `/wwc` links redirect). One person = one login; team ownership is per tournament (F1).
- 23 Nov: B4: website lists newest first; Excel columns oldest to newest. Knockouts are ordered after the league stage and labelled Q1/Elim/Q2/SF1/SF2/Final.
- 23 Nov: C1: scheduled auto-score disabled until IPL 2027.
- 23 Nov: C2: final 2026 data committed to git as an archive.
- 23 Nov: owners bid from their own phones (so owner logins and real-time bidding are needed).
- 23 Nov: the auction runs on the same Railway app.
