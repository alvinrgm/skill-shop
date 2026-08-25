# adlib-creative-intel

Download any advertiser's video ads from the public Meta Ad Library, analyze them
second by second, and rank them by how long the advertiser has kept paying to run
them.

No login and no advertiser account — the Ad Library is public. You do need a
**free Gemini API key**, because watching the videos is the entire point.

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
python3 scripts/probe_gemini.py    # walks you through getting a key (~2 min, free)
python3 scripts/full_run.py --page-id 178024832922517 --slug seed
```

Full instructions: **[SETUP.md](SETUP.md)**

---

## Why this exists

The official Ad Library API returns **metadata only** for commercial ads — page
name, dates, a link. It does not return the creative. (Assets are exposed through
the API only for political/issue and EU-served ads.) So if you want to actually
*look at* what a competitor is running, you are stuck clicking through the web UI
one ad at a time, or paying a creative-intelligence SaaS that scrapes it for you.

This does the scraping part, in about 200 lines, from a public page, anonymously.

## What you get

Three reports per advertiser:

**`strategy-<slug>.md` — the point of the tool.** Every video watched second by
second, then synthesized into their actual content strategy: how long their ads
run and how fast they cut, how they open (and the verbatim first two seconds of
every ad), what they claim, who is on screen, how the formula has shifted between
their older and newer work, and the pattern they keep betting on.

**`profile-<slug>.md` — no API key needed.** The creator/affiliate codes running
in their live copy, every landing destination, CTA mix, placements, launch
cadence by date, duration and aspect-ratio stats, ad copy, and a QA flag for
unrendered `{{template}}` placeholders that reached a live ad.

**`longevity-<slug>.md`** — creatives ranked by days running, and which creative
features cluster in the long-lived ones.

Plus the **raw mp4s**, deduped by creative (one video routinely runs under many
ad IDs, so counting ads inflates everything), and a **ledger** that diffs across
runs — re-run next month and only new creatives download, which answers "what did
they launch since last time."

## The honest limitation, up front

The Ad Library publishes **no impressions, spend, retention, or ROAS**. Nobody has
that data except the advertiser.

So "how long has this ad been running" is the only performance signal available,
and it is a **proxy, not a metric** — confounded by the advertiser's budget, their
always-on habits, seasonality, and plain inertia. A long-running ad tells you what
*they believe*, which is worth knowing and worth testing. It is not evidence that
the same thing will work for you.

Every report this tool writes carries that caveat. Please keep it attached when
you pass findings along. A creative-intelligence tool that lets people quietly
upgrade "they've run it a while" into "it works" is doing harm, not analysis.

## Rules of the road

- The Ad Library is public and needs no login, but **automated access is contrary
  to Meta's Terms of Service.** Occasional low-volume research is unlikely to draw
  more than a rate-limit; scale changes that.
- **Never supply cookies or run this against a logged-in session.** Anonymous,
  public pages only — that is a design constraint, not an oversight.
- Downloaded creatives are someone else's copyrighted work. Analyze them, learn
  from them, don't republish them.
- Read-only: it touches no ad account and sends nothing anywhere.

## License

Software: **CC BY 4.0** — see [LICENSE.txt](LICENSE.txt). Attribution required.
The license covers this software only, never the creatives it downloads.

Contributions and bug reports welcome via the repository's issue tracker.


---
Built and battle-tested at [Rise Growth Marketing](https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=adlib-creative-intel). More free skills, and the story of the systems behind them, at that link.
