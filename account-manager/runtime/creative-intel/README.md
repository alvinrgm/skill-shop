# Creative Intelligence (Meta) — AM Module E

Analyze video ads at the creative level and connect creative choices to
performance. Driven by the `creative-intel` skill (Claude in the loop for the
Meta MCP pulls). Recommend-only.

## The honest frame (read first)
- **Per-second = the CREATIVE** (CV + transcription). **Retention = QUARTILE**
  (Meta exposes p25/p50/p75/p95/p100 + thruplay + 3s only; no per-second curve).
- **Cross-video findings are CORRELATIONAL** (confounded by audience/budget/bid/
  placement), effect-size + sample-size labeled, n<6 flagged. Not causation.
- **Causation requires experiments** → A/B proposals, recommend-only, created only
  on approval.

## Components
| File | Role | Proven |
|------|------|--------|
| `cv_analyze.py` | Gemini per-second video CV → timeline + descriptors | ✅ on real footage |
| `align.py` | map quartile retention + hook onto the creative timeline; find the biggest drop + its cause | ✅ on real retention curves |
| `analyze.py` | cross-video regression: feature → outcome associations, n-flagged, honest caveat | ✅ mechanics |
| `experiments.py` | turn top associations into Meta A/B test proposals (recommend-only) | ✅ mechanics |

## Run (the skill orchestrates; manual pieces below)
```
# 1. (you, via Meta MCP) pull ad metrics + video_ids for the account
# 2. CV each ad's source video:
.venv/bin/python creative-intel/cv_analyze.py --video <mp4> --out /tmp/cv_<ad>.json --label <ad>
# 3-7 are library calls (align/analyze/experiments) — see the creative-intel SKILL.md flow
```
Deps (in the AM venv): `google-genai`, `python-dotenv`, `numpy`. Gemini API key
loaded from the package's own `.env` (`GEMINI_API_KEY`). Default CV model
`gemini-2.5-pro` (falls back to `gemini-2.5-flash`).

## Data sources
- Our ads: match Meta video title → source `.mp4` under your ad-production folder per client.
- Competitors: `ads_library_search` (downloadable library videos).
- Metrics: `ads_get_ad_entities` (quartile retention + ctr + actions-derived CVR/ROAS).
- Comments: via the creative's post (MCP).

## Status / next
v1 core proven on real data. Full cross-video drivers need a corpus run (CV all
of a client's ads) — that's the first real skill invocation. Phase 2: auto comment
sentiment, competitor corpus depth, native chart of the retention-vs-creative
overlay in the report, wiring proposals into the weekly deck.

## Off-switch
Delete `~/.claude/skills/creative-intel/`. These scripts are inert unless invoked.
