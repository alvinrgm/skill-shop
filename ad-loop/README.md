# ad-loop: Static ad loop

Brief in, finished static ads out. A Claude Code skill that takes a brand URL and a
one-round interview and runs a static ad through as many instrumented rounds as it takes
to be genuinely good, or proves it cannot get there and names the ceiling.

Get it:

```bash
git clone --depth 1 https://github.com/alvinrgm/skill-shop
mkdir -p ~/.claude/skills && cp -R skill-shop/ad-loop ~/.claude/skills/ad-loop
cd ~/.claude/skills/ad-loop
```

Install (Python packages go in a `.venv` in this folder; every script uses it once it exists):

```bash
python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -r requirements.txt
cd runtime/static-kit && npm install && npx playwright install chromium && cd -   # Linux: --with-deps
python3 -m playwright install chromium   # same pinned Playwright: reuses that one download
cp .env.example .env            # then add GEMINI_API_KEY
python3 config.py --init        # creates the work root (~/ad-loop-work)
bash doctor.sh
```

Then in Claude Code: `/ad-loop` (or "run the ad loop for <brand>"). Full instructions:
**[SETUP.md](SETUP.md)**. Issues: https://github.com/alvinrgm/skill-shop/issues

---

## What it does

1. **Intake interview.** One batched round of questions, every one with a safe default:
   client and URL, what a win looks like, angle priorities, copy direction, hard rules,
   North Stars, cadence. Answer once and walk away.
2. **URL asset harvest** (`scripts/intake.py`). Pack shots at full resolution, the
   site-exact palette, font names, reviews (Shopify review apps where public), claim
   *candidates* (never approvals), draft pack strings for the print gate, and Meta Ad
   Library page ids for the brand and its competitors. Anything it cannot harvest is
   written down as a `[GAP]`, never invented.
3. **Client layer.** Brand bible, art direction, approved-claims scaffold, quote-grounded
   personas, an asset Library.
4. **The loop.** Diverge on the concept, generate a **volume batch** of plates (15 at 1K by
   default, with a spend guard), run the scripted **triage** cascade over the whole batch
   (physics, legibility, letter-perfect print, global illumination), build the survivors
   into one designed system with the HTML/CSS static-kit, then judge.
5. **The five-instrument judge battery.** A verdict-bank taste twin, a reconstruction-gap
   test (does the ad say the thing at a 1.5s glance?), a blind comparative lineup ("which
   of these was not made by a human design team?"), a craft pass (design laws, glitch pass,
   feed-gate at phone scale), and copy gates (AI-isms scrub, persona resonance, claims).
   Fatal lists, never averaged scores.
6. **Ship bar 85/100**, or a plateau-close after two flat rounds, or the iteration cap. Every
   verdict and learning is written to disk the moment it exists, so the loop compounds
   across sessions.

Statics only. Type is always code-set by the kit, never rendered by an image model.

## Recommend-only by default

The loop **never writes to an ad account on its own**. A shipped concept ends as an upload
packet (images, copy, a ready `asset_feed_spec`, the claims status of every line). If you
connect a Meta Ads connector and explicitly ask, it will create the ad as a **paused
draft** and verify the previews. Turning anything on stays with you.

Claims are legal surface: until a human signs `approved-claims.md`, autonomous builds use
only attributed verbatim customer quotes and text legible on real product photography;
everything else is flagged `[NEEDS APPROVAL]` and goes to the operator only.

## What you need

- Python 3.10+, Node.js 20+, ffmpeg
- A **Gemini API key** (Google AI Studio). It powers all image generation and every vision
  instrument. Image generation is billed per image by Google; the spend guard in
  `config.py` caps each batch.
- Optional: 5-15 North Star ads you consider the bar, and a Meta Ads connector for draft
  uploads.

## What is in the box

```
SKILL.md              the loop doctrine Claude follows (onboarding gate at the top)
config.py             every path and key, the spend guard, --init for the work root
loop-engine/          the scripted instruments + selftest.py (8 checks, no API calls)
scripts/intake.py     the URL harvest
design/design-laws.md the shipping-gate design laws
reference/            judge prompts, rubric, intake, copy steering, logging, build, Meta draft playbook
runtime/static-kit/   HTML/CSS templates + Playwright renderer + inspo harvester + contact sheets
runtime/feed-gate/    in-feed mock and ablation battery (phone scale, chrome, desaturation)
runtime/gen/          Gemini image generator + product-page scraper
runtime/lib/          per-client asset Library + reference-sheet builder
runtime/scrub/        AI-isms copy gate with a starter list
```

## Honest limits

- It ships **no fonts and no reference corpus**. Add the brand's licensed web fonts to
  `runtime/static-kit/fonts/`; build your inspo corpus with
  `runtime/static-kit/tools/harvest_inspo.py`. Automated access to the Ad Library is
  contrary to Meta's Terms of Service: keep it occasional and low-volume, and never
  republish harvested creatives.
- You start with an **empty verdict bank and learnings file**. The taste twin stands down
  until your own verdicts fill the bank; the loop gets sharper as you use it.
- The judges are models. "Ship" means "predicted to survive next to your North Stars", not
  a guarantee. Send the contact sheet to a human.

## License

CC BY 4.0. See [LICENSE.txt](LICENSE.txt).

---

Built by Rise Growth Marketing: https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=ad-loop
