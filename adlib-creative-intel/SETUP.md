# adlib-creative-intel — setup

Download any advertiser's video ads from the public Meta Ad Library, analyze them
second by second, and rank them by how long the advertiser has kept paying to run
them.

The core pipeline runs **anonymously against a public page** — you do not sign in,
you do not need a Meta advertiser login, and harvesting/downloading/reporting needs
no credentials of any kind. That is the whole reason this can be shared. (One
optional step, the per-second creative analysis, needs a Gemini key; see below.)

---

## One-paste install

Paste this into Claude Code (or any coding agent) from inside the package folder:

```
Read SETUP.md and dependencies.yml in this folder, then set me up:
install the Python packages, install the Playwright Chromium browser, and help me
create a Gemini API key (this is the important one — it's what lets the tool
actually watch the videos). Run `bash doctor.sh`, walk me through anything it
reports as missing, then verify the key with `python3 scripts/probe_gemini.py`.
Finish with a run against page ID 178024832922517 and show me the strategy report.
```

Prefer to do it yourself? Four commands:

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
python3 scripts/probe_gemini.py      # tells you exactly how to get a key
bash doctor.sh
```

---

## The API key is the whole point — set it up first

Everything else here just collects videos. **The Gemini key is what lets the tool
watch them**, and watching them is the reason to use it at all.

| Without a key | With a key |
|---|---|
| Which ads exist, how long each has run, the offers and codes, landing pages, CTA mix, launch cadence, durations | All of that, **plus what every ad actually does** — the script, on-screen text, every shot change, the hook, the pacing, the structure — and a synthesized **content-strategy breakdown** across their whole corpus |

Metadata tells you *that* they're running an ad. Only the analysis tells you *what
their content strategy is*.

### Get one (about 2 minutes, free, no credit card)

1. Open **<https://aistudio.google.com/apikey>**
2. Sign in with any Google account
3. Click **Create API key** — the free tier is enough to start
4. Put it in `.env`:
   ```bash
   echo 'GEMINI_API_KEY=your-key-here' >> .env
   ```
5. **Verify it actually works** (not just that it's set):
   ```bash
   python3 scripts/probe_gemini.py
   ```

That probe makes a real API call and, if something's wrong, tells you *which*
thing — invalid key, no model access, quota exhausted, or unsupported region.
Add `--deep` to also push a real video through the File API, which is the exact
path the analysis uses.

**Cost:** the free tier covers occasional runs. A corpus of ~30 videos is roughly
30 API calls. Long videos consume more; if you hit the quota the probe says so
plainly rather than failing mid-run.

**How long a full run takes:** roughly **one minute per video** with the default
`gemini-2.5-pro` (measured on 50-second ads). A 30-video advertiser is about half
an hour. The run prints per-video progress and a running ETA, so you can watch it
work. Two things worth knowing:

- **Every analysis is cached.** If a run is interrupted, or you hit the quota,
  re-running skips everything already analyzed and resumes where it stopped.
  Nothing is wasted and nothing is paid for twice.
- **`--model gemini-2.5-flash`** is markedly faster and cheaper across a large
  corpus, at some cost in precision. Reasonable when you are surveying many
  advertisers; use the default `pro` when the teardown matters.

---

## What you need

| What | Required? | Why | Where to get it |
|---|---|---|---|
| Python 3.9+ | yes | runs everything | preinstalled on macOS/Linux |
| `playwright` + `requests` | yes | harvest + download | `pip install -r requirements.txt` |
| Chromium browser | yes | renders the Ad Library page | `python3 -m playwright install chromium` (~150MB, free) |
| A Meta Page ID | yes | names the advertiser to analyze | see below — it is in the URL |
| `ffprobe` (ffmpeg) | no | duration / resolution / aspect stats in the profile | `brew install ffmpeg` · https://ffmpeg.org/download.html |
| **Gemini API key** | **yes** — it's the point | **watching the videos**: script, on-screen text, hooks, pacing, content strategy | https://aistudio.google.com/apikey (free, ~2 min — see above) |

### Finding a Page ID (30 seconds, no account)

1. Open <https://www.facebook.com/ads/library/>
2. Search the advertiser and click into their page
3. Copy the `view_all_page_id=` number out of the browser URL

That number is the only argument the pipeline needs.

---

## First run

Longevity report only, no key required:

```bash
python3 scripts/full_run.py --page-id 178024832922517 --slug seed --no-cv
```

With creative analysis (after adding `GEMINI_API_KEY` to `.env`):

```bash
python3 scripts/full_run.py --page-id 178024832922517 --slug seed --cv-limit 6
```

Output lands in `outputs/longevity-<slug>.md`; videos and metadata in `data/<slug>/`.

---

## What it does

1. **harvest** — renders the advertiser's public Ad Library page and reads the ads out
   of the page's own JSON, including the signed video URLs
2. **ingest** — dedupes by *creative* (one video often runs under many ad IDs),
   downloads each mp4 once, records everything in a ledger
3. **analyze** *(optional)* — per-second breakdown of the longest-running creatives:
   script, on-screen text, shots, hook archetype, pacing
4. **report** — a longevity table plus which creative features cluster in the
   long-running ads

Re-run the same page later and only new creatives download. **That diff is the
signal**: it answers "what did they launch since last time."

---

## Read this before you trust a number

The Ad Library publishes **no impressions, spend, retention, or ROAS** for
commercial ads. Nobody has that data but the advertiser.

So the only observable proxies are **how long an ad has been running**, **how many
ad IDs share one creative**, and **platform spread**. A long-running ad means the
advertiser keeps paying for it — which is confounded by their budget, their
always-on habits, seasonality, and plain inertia.

Every finding is a **hypothesis about what they believe**, worth testing on your
own account. None of it is evidence that the same thing will work for you. The
tool labels this on every report it writes; please keep that label attached when
you pass findings on.

## Rules of the road

- The Ad Library is public and requires no login, but **scraping it is against
  Meta's Terms of Service**. Occasional, low-volume research is very unlikely to
  attract anything worse than a rate-limit. Scale it up and that changes.
- **Never point this at a logged-in session or supply your own cookies.** It is
  built to run anonymously, against public pages only, and it should stay that way.
- Downloaded creatives are someone else's copyrighted work. Analyze them, learn
  from them, do not republish them.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `could not launch chromium` | `python3 -m playwright install chromium` |
| Harvest returns 0 creatives | The page may run no active *video* ads in that country. Try `--country GB`, or check the page ID. |
| `GEMINI_API_KEY not found` | Only affects the analysis step. Add it to `.env`, or pass `--no-cv`. |
| Downloads fail with 403 | Signed URLs expire (~5 days). Re-run — it re-harvests fresh URLs. |
| Slow harvest | Normal: it scrolls until the page stops growing. Cap with `--max-scrolls 20`. |

Re-check your setup anytime with `bash doctor.sh`. Re-audit the package itself with
`python3 verify_portable.py .`
