# skill shop

Free, working Claude Code skills from [Rise Growth Marketing](https://www.risegm.com/skills?utm_source=github&utm_medium=readme&utm_content=root). These are tools we built for our own agency and run daily on real accounts, packaged so they run on your machine, your accounts, your data. Each one installs with a paste, checks its own dependencies (`doctor.sh`), and walks you through setup.

## The skills

| Skill | What it does |
|---|---|
| [adlib-creative-intel](adlib-creative-intel/) | Harvest any brand's ads from the Meta Ad Library (videos included), run computer vision over every frame, and get a creative-intelligence report: hooks, formats, claims, pacing. Works on competitors |
| [account-manager](account-manager/) | The AI account-manager: weekly reporting decks drafted from live ad data, daily data-health checks. The system we built when our account manager left |
| [adgen-vertical-ad](adgen-vertical-ad/) | End-to-end vertical video ad production: PDP URL in, finished 9:16 ad out: script, characters, scenes, video gen, audio, editable timeline |
| [multi-size-adapter](multi-size-adapter/) | One master creative → every ad size you need, layout-aware, not a dumb crop |
| [gsuite-bridge](gsuite-bridge/) | Create fully formatted Google Docs, Sheets, and Slides from Claude Code: headings, tables, styled decks, via your own Apps Script bridge |
| [dialectical-debate](dialectical-debate/) | Stress-test any claim or decision: opposing agents investigate independently, cross-examine, and return a confidence-rated verdict |
| [strategy-crystallizer](strategy-crystallizer/) | Force any brand or business question through Rumelt's strategy kernel: falsifiable one-sentence thesis, coherent actions, explicit refusals, graded out of 70. Refuses fluff, demands diagnosis before action |

## Adding to the shop

`catalog.json` is the one list of what's published here, and risegm.com/skills builds its cards from it. A new folder needs a catalog entry (and a `SETUP.md`) or the check fails. Run `python3 scripts/check_catalog.py` before pushing.

Every package must also be labeled `trust_level: public` and carry a leak-audit receipt in `.leak-audit/<package>.txt` that matches its current contents. `scripts/check_public.py` checks both in CI, and a Claude Code hook in `.claude/settings.json` (`scripts/publish_guard.py`) refuses commits, pushes and merges that would fail it. Any edit to a package needs a fresh audit and receipt before it can ship.

## Install

Each skill folder has a `SETUP.md` with a one-paste install and a `doctor.sh` that verifies your environment. Start there. Every skill assumes only Claude Code and walks you through anything else it needs.

## Who's behind this

[Rise Growth Marketing](https://www.risegm.com/?utm_source=github&utm_medium=readme&utm_content=root) is the first superlinear agency. We run paid media for DTC brands with senior operators augmented by systems like these; we also [build custom AI marketing systems](https://www.risegm.com/ai-systems?utm_source=github&utm_medium=readme&utm_content=root) against your workflows, fixed scope, you own everything at handoff.

These free skills are the generic versions. The paid work is building the version wired to your data, your accounts, and your team's workflow.

## License

Each skill carries its own license file where present; adlib-creative-intel is CC-BY. Use them, fork them, ship them. attribution appreciated.
