---
name: adlib-creative-intel
description: >-
  Download and analyze any advertiser's video ads from the public Meta Ad Library.
  Harvests a page's active video ads headlessly (no login, no ad account, no API
  key), dedupes by creative, downloads the raw mp4s, optionally runs a per-second
  creative breakdown (script, on-screen text, hook, pacing), and ranks everything
  by longevity — how long the advertiser has kept paying to run it. Triggers on:
  "what ads is <brand> running", "analyze <brand>'s ads", "competitor creative
  teardown", "download ads from the Ad Library", "/adlib-creative-intel <brand>".
  Read-only research: it never touches an ad account and never publishes anything.
---

# Ad Library creative intelligence

## FIRST RUN — onboarding gate

If `.onboarded` does NOT exist in this folder, do this BEFORE any analysis:

1. Run `bash doctor.sh` and read the ❌ lines.
2. Walk each ❌ one at a time. For each: say what it powers, give the link, and
   offer to run the fix:
   - **Python packages** → offer to run `pip install -r requirements.txt`
   - **Chromium** → offer to run `python3 -m playwright install chromium`
     (~150MB, free, one time)
   - **ffprobe** (optional, never a blocker) → adds duration/resolution/aspect
     stats to the advertiser profile. Offer `brew install ffmpeg` (or
     `apt install ffmpeg`). Everything else works without it.
   - **Gemini key — REQUIRED, and the most important step. Do not soft-pedal
     it.** This is what lets the tool WATCH the ads. Without it the user gets
     metadata (which ads exist, how long they ran); with it they get what the
     ads actually DO and a content-strategy breakdown. That is the reason to
     use this tool at all. Walk them through it actively:
       1. Send them to <https://aistudio.google.com/apikey>
       2. Sign in with any Google account → **Create API key** (free, no card)
       3. Ask them to paste it, then YOU write it to `.env`. Never echo it back.
       4. Run `python3 scripts/probe_gemini.py` — a REAL API call, not an
          "is the variable set" check. If it fails it names the cause (invalid
          key / no model access / quota / region). Fix and re-run.
     If they decline, say plainly what they are giving up and that `--no-cv`
     gives them the metadata-only path — then respect the choice and move on.
3. Re-run `bash doctor.sh`. When all REQUIRED deps are ✅, write `.onboarded` and
   offer a first run.
4. Ask which advertiser they want, and help them get the Page ID: open
   <https://www.facebook.com/ads/library/>, search the advertiser, click into the
   page, copy `view_all_page_id=` from the URL. No account needed.

On later runs `.onboarded` exists — skip straight to the work.

## Running it

One command does everything:

```bash
python3 scripts/full_run.py --page-id <ID> --slug <name> [--cv-limit 6] [--no-cv]
```

- `--no-cv` — longevity only, no API key needed
- `--cv-limit N` — analyze the N longest-running creatives (default 5)
- `--country GB` — non-US Ad Library (default US)

`--cv-limit` defaults to **0, meaning every creative gets watched**. A content
strategy is a property of the whole corpus, so do not sample it unless the user
asks or quota forces it.

Every run writes THREE reports to `outputs/`:
- `strategy-<slug>.md` — **the deliverable.** Their content strategy synthesized
  across every analyzed video: format, how they open, what they claim, craft,
  how it has shifted over time, and the formula they keep betting on. Requires
  the API key.
- `profile-<slug>.md` — offers and creator codes, landing destinations, CTA mix,
  placements, launch cadence, format stats, ad copy, QA flags. Needs no key.
- `longevity-<slug>.md` — creatives ranked by days running, plus which features
  cluster in the long-running ads.

Individual stages, if you need them:

```bash
python3 scripts/harvest.py --page-id <ID> --out data/harvest.json
python3 scripts/adlib_fetch.py ingest --in data/harvest.json --page-slug <name>
python3 scripts/describe.py --page-slug <name>      # no-key profile
python3 scripts/adlib_fetch.py report --page-slug <name>
python3 scripts/cv_analyze.py --video data/<name>/<key>.mp4 --out cv.json
```

## What you get WITHOUT an API key

Assume you can never watch a single frame. You still get, from metadata and the
video files alone: the **creator/affiliate codes** they are actively running (the
roster of partners they pay), **every landing destination**, the **CTA mix**, the
**placements**, the **launch cadence** (their testing tempo, by date), **duration,
resolution and aspect ratio** for each video, the **ad copy**, and a **QA flag**
for unrendered `{{template}}` placeholders that reached a live ad.

Campaign taxonomy via `utm_campaign` is a bonus that **many advertisers do not
expose** — some put their whole naming scheme in the link, others use non-utm
parameters or none. Its absence says nothing about them; do not read into it.

`compete.py` is a library: `analyze_competitors(records)` finds which creative
features cluster in long-running ads; `compare_to_us(theirs, ours)` diffs two
advertisers — harvest your own page the same way to use it.

## How it works, and why it works this way

The official Ad Library API returns **metadata only** for commercial ads — no
creative assets (those are exposed only for political/issue and EU-served ads).
So the videos come out of the rendered public page, where they appear as signed
CDN URLs: SD in the `<video>` tags, HD in the page's own embedded JSON.

Three approaches were tested; save yourself the time:
- **The API** — no assets for commercial ads. Dead end for creative.
- **yt-dlp** — ships a `facebook:ads` extractor, but Meta answers unauthenticated
  requests with a 403 client challenge, and TLS impersonation does not fix it. It
  works only with a logged-in session's cookies, which this tool deliberately
  refuses to require.
- **Headless browser** — works, anonymously, against the public page. This is it.

**Dedupe by creative, never by ad.** One video routinely runs under many ad IDs
(placement and collation variants). Counting ads inflates everything; the unit of
creative analysis is the video asset.

**The ledger is the point.** Re-running a page only downloads what is new, so the
diff answers "what did they launch since last time" without any extra machinery.

## Honesty rules — enforce these on every output

The Ad Library publishes **no impressions, spend, retention, or ROAS** for
commercial ads. That data does not exist outside the advertiser's own account.

1. **Longevity is a proxy, not a metric.** Label it as one, every time. It is
   confounded by budget, always-on strategy, seasonality, and inertia.
2. **A finding is a hypothesis about what THEY believe** — worth testing on your
   own account, never evidence that it will work for you.
3. **Never present a competitor pattern as a directive to copy.** They have a
   different product, margin, audience, and funnel. If a pattern contradicts
   something you already know or have already tested, that is a flag, not a
   recommendation.
4. **Say what you did not cover.** Harvest caps, skipped analyses, and zero-result
   pages are real answers — report them plainly rather than padding.

## Rules of the road

- The Ad Library is public, but scraping it is against Meta's Terms of Service.
  Occasional low-volume research risks little more than a rate-limit; scale
  changes that calculus.
- **Never supply cookies or point this at a logged-in session.** Anonymous,
  public pages only.
- Downloaded creatives are someone else's copyrighted work. Analyze and learn;
  do not republish.
- Read-only by design: it touches no ad account and sends nothing anywhere.
