# Ad creative library

A Claude Code skill that runs static ad production out of **one Figma file per brand**. Figma is
where ads are made and edited, layer by layer. Disk is where the facts, data and state live. The
file compounds: every batch reuses the template shelf, every test result moves the roadmap, and
every verdict sharpens the learnings page the next batch is planned from.

You need **your own Figma account** (connected through the Figma MCP, Full or Dev seat on a paid
plan) and **a Gemini API key**. Full instructions: **[SETUP.md](SETUP.md)**.

```bash
git clone --depth 1 https://github.com/alvinrgm/skill-shop
mkdir -p ~/.claude/skills && cp -R skill-shop/ad-library ~/.claude/skills/ad-library
cd ~/.claude/skills/ad-library
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
# edit .env: fill in the GEMINI_API_KEY= line with your key
python3 scripts/probe_gemini.py                            # a real (free) call that proves the key
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin install figma@claude-plugins-official        # the Figma MCP, signed in as you
bash doctor.sh; python3 scripts/selftest.py               # selftest: every offline-testable script
```

`doctor.sh` shows Figma MCP as ❌ until Claude has confirmed the Figma tools in a session (a shell
cannot see them); SETUP.md covers that last step and the `.onboarded` marker.

Then in Claude Code: *"build the ad library for <brand>, site <url>"*.

## What one brand's Figma file holds

| Page | What's on it |
|---|---|
| **Brand kit** | colour and spacing variables, text styles in the closest Figma fonts to the site, a `Label` component per verified claim, the proof bar |
| **Assets** | the real pack cutouts as components, the brand's own site photography (crawled at full resolution, classified, one section per category), approved generated plates |
| **Templates** | direct-response formats (offer card, us vs them, benefit callouts, testimonial, question hook, stats, myth vs fact, in-use hero, ...) as component sets with a 4:5 and 9:16 variant and editable properties |
| **Shot list** | every scene the brand needs, with the templates and angles each one feeds |
| **Roadmap** | the angle tree: every past Meta ad mapped onto it, what's tested vs greenfield, the test queue |
| **Creative learnings** | winning and losing traits with their evidence, and how each is enforced in the templates |
| **B01, B02, ...** | one page per batch: a test card per ad (hypothesis, budget, keep and kill lines) and the ads as template instances in both ratios, exported at 2x |

## What makes it different from "generate an ad"

- **Every layer stays editable.** Headline, labels, badges and the pack are real Figma layers and
  component properties. Only the background photo plate is generated. A designer (or you) edits
  in Figma; nothing is baked into a picture.
- **The pack is never trusted to a model.** Image models garble fine print and invent claims on
  packaging. Every generated plate that shows the pack goes through a **letter-perfect print
  gate** (a vision model transcribes, a deterministic scorer compares with the real printed
  strings) and is repaired with the real label when it fails.
- **Claims are gated.** Every line of copy is checked against a truth ledger of what the brand
  can prove, before it reaches Figma.
- **Ship-grade resolution.** Plates are generated at 4K and exported at 2x, because a 1K plate
  under sharp vector type reads as grain on a phone. A QA script enforces it.
- **Tests, not one polished ad.** Batches of 2-3 testable ads, one variable per pair, each with a
  written hypothesis and keep/kill lines; results feed the roadmap and the learnings.

## What it does not do

- It does not write to your ad account. You upload the exports (it hands you the files, copy and
  ad names); `learn.py` only reads.
- It does not make video ads or landing pages.
- It does not decide winners from Meta's numbers. Verdicts come from your own attribution read
  or a finished test; the script only proposes.

## License

**CC BY 4.0**, see [LICENSE.txt](LICENSE.txt). Attribution required. Use only brand material you
have the right to use.

Contributions and bug reports welcome: <https://github.com/alvinrgm/skill-shop/issues>.

---
Built by Rise Growth Marketing: https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=ad-library
