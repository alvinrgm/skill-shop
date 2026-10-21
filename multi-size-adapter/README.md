# Multi-Size Creative Adapter

Takes an ad you have already made and rebuilds it for other placements, so each format looks
designed for that shape rather than cropped or padded from another one. Your copy is kept
word for word.

**Start here: [SETUP.md](SETUP.md).** It has a one-paste setup line and everything you need.

## How you give it an ad
Claude asks once, on first run, where your ad files usually live — then you can just say
"adapt the newest coffee ad" and it finds the file. **One thing worth knowing: dragging an
image into the chat window is not enough.** Claude can see a pasted image but cannot work from
it; the tool needs the actual file. Point it at a file or a folder (dragging a file onto the
Terminal window pastes its path), or just name the file and let Claude find it in your
creatives folder. Adapted formats land wherever you told it to put them — pick somewhere in
your own working folders, not inside this package.

## What you get
One folder per format, plus a `review-sheet.md` per creative recording what was checked and
what still needs a person.

| Format | Shape | Where it runs |
|---|---|---|
| Square | 1:1 | Instagram/Facebook feed, LinkedIn |
| Portrait | 4:5 | Instagram/Facebook feed |
| Story / Reel | 9:16 | Instagram, TikTok, Facebook Stories and Reels |
| Landscape | 16:9 | YouTube, display, link posts |

Other shapes are available on request; Claude explains the tradeoff first.

## What it is not
These are **designer-ready starting points, not finished ads.** Every format still needs a
design pass. Two things always need a person before anything ships:

1. **The legal fine print is deliberately left blank.** AI cannot render small legal text
   reliably, so this tool never generates it. Paste yours back in during finishing.
2. **A brand QA pass** on typesetting and spacing.

## When NOT to use this
Straight answer, because every run costs money:

- **When the source has a photographed person or a real product shot.** Re-composition
  redraws the image, so faces and packaging change. Fine for graphic/typographic ads; not for
  anything where a specific human or SKU must stay exactly itself.
- **When the ad is photo-heavy AND carries a dense legal block.** Suppressing the legal text
  is most reliable on graphic/flat ads; on busy photo compositions the model sometimes
  regenerates a garbled version of it. The tool flags this and names the file `NEEDS-LEGAL`,
  but it means more of these need a regenerate-or-fix pass.
- **When your copy is legally exact and small.** Large headline text comes through reliably;
  small type is where generation corrupts things subtly. That is why legal is never
  generated. If a regulated claim is set in small type in the body, a mechanical resize is
  safer than a re-composition.
- **When the layout must stay on a strict grid in a licensed typeface.** Output is off-grid
  and off-font by construction, so a designer would rebuild the type anyway.
- **When the copy is already too long for the target placement.** This tool keeps your copy
  word for word and will happily generate a format the text does not fit. Check the limits in
  `standard-sizes.md` first.
- **At volume.** Every output gets opened and checked, so about 10 creatives is a sensible
  session. Hundreds of creatives a month is not what this is.

In those cases a plain mechanical resize plus a designer is the better tool, and it is free.

## What it costs
About $0.134 per generated image, billed to your team's Google account. Claude shows you the
image count and the estimate before every batch and waits for your go-ahead. Claude's own
usage is billed separately under your Claude subscription.

## Files
| File | What it is |
|---|---|
| `SETUP.md` | Setup, the team-lead key/billing walkthrough, and how to run it |
| `SKILL.md` | The workflow Claude follows (you do not need to read this) |
| `standard-sizes.md` | The four formats, safe zones, and copy limits |
| `doctor.sh` / `doctor.ps1` | Health check (Mac/Linux and Windows) |
| `config.example.yml` | Template for your key. Copy to `config.yml` (Claude does this for you) |
| `samples/` | A worked example so you can see what a good run produces |
| `scripts/` | The engine. You never call it directly; Claude runs it |
| `scripts/selftest.py` | "Does this actually work?" — one test image, ~$0.13. Ask Claude to "run the self-test" |

## Stopping, and cleaning up
Nothing here runs on a schedule or in the background. It only does something when someone
asks Claude to, so "stopping" is just not using it. To remove it completely:

1. **Delete this folder.** That is the whole uninstall. Nothing was installed elsewhere on
   your machine, no background job was registered, and nothing was added to any account.
2. **Your generated files are yours** — if you want to keep any, move `outputs/` somewhere
   else first.
3. **Retire the key if you are done for good.** The Gemini key lives in `config.yml` inside
   this folder and is a live payment credential. Deleting the folder removes your copy, but
   the key still exists on your team's Google account. If someone leaves the team, or the key
   is ever pasted somewhere it should not be, the team lead should delete it in Google AI
   Studio (**Get API key** -> the key -> delete) and issue a new one. Everyone then pastes the
   new one to Claude once.

## Privacy
Each generated format sends the source creative and a resize instruction to Google's Gemini
API. Nothing else leaves your machine, and nothing is published anywhere. See SETUP.md for the
full disclosure and the paid-tier data policy.


---
Built and battle-tested at [Rise Growth Marketing](https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=multi-size-adapter). More free skills, and the story of the systems behind them, at that link.
