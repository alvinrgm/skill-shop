---
name: ad-library
description: >
  Ad creative library: a Figma system for STATIC ads, project manager and designer in one. Each
  brand gets ONE Figma file holding its brand kit (variables, text styles, claim labels, real pack
  cutouts), asset bank (the brand's own site photography plus generated photo plates), template
  shelf (direct-response formats in 4:5 and 9:16 with component properties), shot list, creative
  testing roadmap (angle tree, done vs greenfield, test queue), creative learnings (winning and
  losing traits, refreshed from Meta by script), and one deliverables page per batch. Every layer
  stays editable; only the photo plates are generated (Gemini image models on your key). Triggers:
  "/ad-library", "build the ad library for <brand>", "set up <brand> in figma for ads", "next batch
  for <brand>", "make statics for <brand>", "update the learnings", "refresh the roadmap", "what
  should we test next", "add to the shot list", "review my figma comments", "export batch <id>".
  NOT video ads, NOT landing pages.
---

# Ad creative library

<!-- ════════════════════════════════════════════════════════════════════════
     FIRST-RUN ONBOARDING GATE. Generated from dependencies.yml; keep it in
     sync with doctor.sh.
     ════════════════════════════════════════════════════════════════════════ -->

## First run? Onboard before you do anything else

**Gate:** if `.onboarded` does NOT exist in this skill's folder, do NOT start the workflow. Run
onboarding first. If `.onboarded` exists, skip this section. (Say "re-run setup", or delete
`.onboarded`, to onboard again.)

1. **Health check.** Run `bash doctor.sh` (Windows: `powershell -ExecutionPolicy Bypass -File doctor.ps1`).
   Read the ✅/❌ list. Every dependency is described in `dependencies.yml`.
2. **Walk each ❌ one at a time**, in this order. Say what it powers, give the link, offer to do it:
   - **Python packages** (Pillow, numpy) → offer a virtual environment in this folder (systems with
     an externally-managed Python refuse a bare `pip install`): `python3 -m venv .venv &&
     .venv/bin/pip install -r requirements.txt` (Windows: `.venv\Scripts\pip`). doctor.sh and the
     scripts use `.venv` automatically when it exists.
   - **Gemini API key (required)**. It generates the photo plates and runs the print gate that
     catches garbled or invented print on a generated pack. Send them to
     <https://aistudio.google.com/apikey> → **Create API key**. Ask them to paste it; YOU copy `.env.example`
     to `.env` (if there is no `.env` yet) and fill in its existing `GEMINI_API_KEY=` line (edit
     it, do not append a second one). Never echo the key back. Verify
     with `python3 scripts/probe_gemini.py` (a real API call; free). Image generation is billed
     by Google on their key, roughly $0.13 per 1K-2K plate and $0.24 per 4K plate.
   - **Figma MCP (required)**, on their OWN Figma account. It is how every page, template and ad
     is built and exported. Recommended (adds the MCP and its skills): add the official
     marketplace first, `claude plugin marketplace add anthropics/claude-plugins-official`, then
     `claude plugin install figma@claude-plugins-official`. Fallback: `claude mcp add --transport http figma https://mcp.figma.com/mcp`,
     then `/mcp` → figma → authenticate in the browser. Restart Claude Code if the tools do not
     appear. **Verify by checking that the `use_figma`, `create_new_file`, `upload_assets` and
     `download_assets` tools are available to you, then call `whoami`.** Seat matters: a Full or
     Dev seat on a paid plan (Professional: 200 MCP calls a day); Starter plans and View/Collab
     seats get 6 calls a MONTH, which cannot build a library. Plans:
     <https://www.figma.com/pricing/>. No account yet: <https://www.figma.com/signup>. doctor.sh
     cannot see MCP tools, so it shows Figma MCP as ❌ until YOU have confirmed the tools.
   - **curl** → only for posting files to the URLs `upload_assets` returns. Preinstalled on
     macOS, Linux and Windows 10+.
   - **OpenCV + SciPy (optional)** → only for `label_composite.py`, the real-label repair on a
     generated plate. Offer `.venv/bin/pip install -r requirements-repair.txt` (same `.venv`). Skip if
     they will only use plates without the pack, or real photography.
   - **Meta read token (optional)** → `learn.py` maps every past ad onto the angle tree and reads
     batch tests. Their OWN token with `ads_read`, from <https://developers.facebook.com/tools/explorer/>
     (or a System User token from Business Settings for one that does not expire), plus their ad
     account number. Write `META_ACCESS_TOKEN` and `META_AD_ACCOUNT_ID` to `.env`. Without it the
     roadmap starts all-greenfield and verdicts are entered by hand from their own reports.
   - **Figma token for comments (optional)** → `figma_comments.py` reads and answers reviewer
     comments (the MCP has no comment tools). Figma → Settings → Security → Personal access
     tokens, scopes File content: read, Comments: write. Docs:
     <https://developers.figma.com/docs/rest-api/authentication/>. Write `FIGMA_TOKEN` to `.env`.
3. **Offline self-test.** `python3 scripts/selftest.py` must end `selftest: N/N passed`.
4. **Mark done.** Once YOU have confirmed the Figma tools are present (and `whoami` answered),
   re-run `bash doctor.sh --figma-confirmed` (Windows: `doctor.ps1 -FigmaConfirmed`). Only when it
   exits 0, write `.onboarded` (`date > .onboarded`). Then tell them the first line to type:
   *"build the ad library for <brand>, site <url>"*.

<!-- ═══════════════════════ END ONBOARDING GATE ═══════════════════════════ -->

## Paths and the two sources of truth

`$AD_LIBRARY_HOME` (default `~/ad-library`) holds one folder per brand: `$AD_LIBRARY_HOME/<brand>/`.
`scripts/init_brand.py <brand> --name "..."` creates it. Below, `<B>` means that folder and
`scripts/` means this skill's `scripts/` folder.

- **Disk = facts, data and state.** The truth ledger (every claim, offer and quote with its
  proof), the pack's real printed strings, copy rules, the angle tree, traits, the shot list,
  the asset Library, every id the Figma file returned (`<B>/state.json`). Disk feeds Figma; it
  never reads design back from it.
- **Figma = design.** Layout, type, sizes, colour, image choice. Every edit, by Claude or a
  person, happens there, layer by layer, like a layered image editor.

The file compounds: every batch reuses the shelf, every test result moves the roadmap, every
verdict sharpens the learnings page the next batch is planned from.

## 0. Every session starts here, in this order

1. **Read `<B>/state.json`.** File key, page ids, template and component ids, batches, today's call
   count, lessons. Never guess an id; never re-derive what the file already records.
2. **Read open Figma comments** (`python3 scripts/figma_comments.py pending <brand>`, if a
   `FIGMA_TOKEN` is set; otherwise ask the person whether they left comments). Act on each, then
   reply in Figma (`figma_comments.py reply`). `client_meta.node_id` is often the PAGE root: use
   `node_offset` against the root's layout to find the card or ad it sits on. Re-check before
   the final report. Resolving happens in the Figma UI once the fix is live.
3. **Plan the Figma call budget.** Pro plan, Full or Dev seat: 200 MCP tool calls a day, 10 a
   minute (Organization 200/day, Enterprise 600/day; `whoami` is exempt). One `use_figma` per
   page or per batch, the page switched once per call, multi-page work fanned out in parallel.
   Log the count in `state.json.mcp_calls` at the end.
4. **Read the learnings:** `<B>/learnings/traits.json` and the newest `<B>/learnings/refresh-*.md`.
   Plan from them.
5. **Load the `figma-use` skill before any `use_figma` call** (it ships with the Figma plugin, or
   is served by the Figma MCP as a resource). Paste `reference/figma-kit.js` at the top of every
   template-build call, with the `KIT` object filled from `state.json`.

## 1. The file and its disk mirror

| Figma page | holds | source of truth on disk |
|---|---|---|
| `Brand kit` | variables (colour, spacing, radius, safe zones), text styles, `Shadow/Pack`, the `Label` set (one claim pill per verified ledger row, the ledger id in each description), the proof bar | `<B>/brand/truth-ledger.jsonl`, `<B>/brand/` |
| `Assets` | `Asset / Pack / <SKU>` real cutouts; a core section (pack, offer card, generated examples); the site crawl as components, one section per category | `<B>/brand/site-photography/` (`index.json`, `classification.json`, `INVENTORY.md`), `<B>/library/` |
| `Templates` | `Template / NN <name>` sets, `Ratio` variant 4x5 + 9x16, exposed TEXT / BOOLEAN / INSTANCE_SWAP properties, verdict badges, an index card | `reference/figma-kit.js` (the build helpers) |
| `Shot list` | every scene the brand needs photographed or generated, by section, with priority, the templates and angles it feeds, source (have / shoot / either) and generated examples | `<B>/shotlist/shotlist.json` |
| `Roadmap` | the angle tree (angles, sub-angles) with status, verdict, spend, past creatives, hooks, the test note, and the test queue | `<B>/roadmap/angles.json`, `<B>/roadmap/tracker.json` |
| `Creative learnings` | winning and losing traits with evidence and how each is applied | `<B>/learnings/traits.json`, `<B>/learnings/refresh-*.md` |
| `B<nn> · mm/dd · <batch>` | one page per batch: cover (a test card per ad, the read rule, the VERIFY list), the ads as template instances in both ratios | `<B>/runs/b<nn>/` (exports, `qa.json`), `state.json.batches` |

Ownership: these pages are built by this skill. A frame a person made is theirs: never rebuild
it, never detach it, never "tidy" it.

## 2. Library first

Every brand has ONE asset Library at `<B>/library/` (`library.json` + files by type: product,
location, character, plate, reference), driven by `scripts/asset_library.py`
(`init`, `register-packs`, `add`, `list`, `get`, `refs`, `gate --print`, `set`, `use`). Before
making or hunting for any reference image, ask it; after making a keeper, register it. Only
`approved` entries come back from `refs`; a draft never silently becomes the reference for a paid generation. Record
every use (`use --by <batch>`). Reference sheets: `scripts/ref_sheet.py --type product|location|character`
(product sheets are print-gated; a location also writes the canonical 9:16 plate, the
continuity lock for every later plate in that place). Every approved plate goes into the Library
(`add --type plate`) with its Figma component id (`set figma_node_id=`). The Assets page mirrors
`status=approved` entries.

## 3. Modes

### ONBOARD (new brand, about 12-20 Figma calls)
1. **Disk first.** `python3 scripts/init_brand.py <brand> --name "<Name>" --site <url>`. Then, with
   the person, replace the examples: every claim, offer and quote the brand may use into
   `brand/truth-ledger.jsonl` (with its source; unproven = `candidate`), every line printed on
   the real pack into `brand/pack-strings.json`, banned words and hedges into
   `brand/copy-rules.json`, the brand's angles into `roadmap/angles.json` (a `match` regex per
   sub-angle against their Meta ad names).
2. **Photography.** `python3 scripts/crawl_site.py <brand> --site <url> --page /pages/about ...`
   (Shopify `products.json` at full resolution, plus the `<img>` and `og:image` of the pages you
   list). Look at every image; classify each (category, SKU, text burned in, ad-usable, pack era)
   into `brand/site-photography/classification.json`; write `INVENTORY.md` with the gaps.
3. **Pack cutouts.** For each SKU's straight-on product photo on a plain background:
   `python3 scripts/cutout.py <brand> <photo> --name <sku>` → `brand/packs/pack-<sku>.png`. A pack
   photographed in a scene: use Figma's own Remove background on the image instead, and save the
   PNG into `brand/packs/`. Look at each at full size. Then `asset_library.py register-packs <brand>`.
4. **The file.** `create_new_file` (design file, named `<Brand> · Ad Library`; it lands in the
   person's drafts, they move it into a team project so others can edit). Record `file_key`.
5. **Foundations (1-2 calls):** variables + text styles from the site's fonts (the closest fonts
   in Figma's library) and palette (read the site's CSS for the exact hex values, do not
   eyeball); the `Label` set from the ledger's verified rows; pack cutouts as `Asset / Pack / <SKU>`.
6. **Asset bank:** upload the crawl in batches of 60 or fewer, named `{category}__{label}__r###` so
   layer names carry the index, then one call turns them into components in category sections.
   `upload_assets` returns upload URLs; POST each file to ITS url with curl, pairing file and
   url explicitly (an off-by-one loop puts every image in the wrong slot).
7. **Templates:** build from `reference/figma-kit.js`, 2-4 sets per call. Every template passes
   `check()` in both ratios before it is kept. A standard shelf: offer card, us vs them,
   before/after, testimonial, review wall, lifestyle, benefit callouts, statement, question hook,
   founder letter, stats, myth vs fact, what you get, reasons to switch, search bar, in-use
   hero. Judge the shelf against `reference/design-laws.md`.
8. **Roadmap, Shot list, Creative learnings pages** (see LEARN, PLAN, SHOOT). Write `state.json`
   as you go: every id the calls return.

### LEARN (keep the learnings current; zero Figma calls for the refresh itself)
- `python3 scripts/learn.py <brand>` pulls every Meta ad with spend (read-only), re-maps them onto
  the angle tree **keeping recorded verdicts**, reads launched batches, and writes
  `learnings/refresh-<date>.md`. It changes no verdict. `--no-meta` builds the tracker from
  `angles.json` alone (onboarding, or no Meta connection).
- **Verdicts move only on evidence:** the person's attribution read (new customers per $1k from
  whatever tool they trust), a matched-spend comparison, or a finished batch test. Never CTR.
  Write the change into `traits.json` with the evidence, the date and, if a person gave the
  verdict, their exact words.
- Then **SYNC** the Roadmap and Creative learnings pages (one call each).
- Weekly is a good cadence; run it by hand or from cron. The Figma sync stays interactive.

### PLAN (the roadmap and the test queue)
- The angle tree in `roadmap/angles.json`: top-level angles (taste, health, convenience, price,
  origin, social proof, seasonal, ...), each with sub-angles and the name regex that maps past
  ads onto it. Status: greenfield / light / tested / live, from Meta (or greenfield without it).
  **Name every new ad so a `match` catches it** and so its batch tag (`B01`) is in the name.
- Hooks per sub-angle come from the ledger and real customer quotes. Customer-facing copy is
  written or approved by the person (or their copywriter); Claude may draft on request, and
  every line passes `scripts/copy_gate.py <brand> <copy-file>` before it goes into Figma.
- Test cadence (adjust to budget): 2-3 new ads a week, about 10% of spend, one ad set. One
  variable per pair (same photo and layout, only the headline changes). Every test has a
  written hypothesis, the traits it uses, a budget, a keep line and a kill line.

### SHOOT (shot list and plates)
- The shot list is planned from the roadmap: every shot names the templates and angles it feeds.
  The biggest gap is usually the CURRENT pack in a real scene; say so at the top of the page.
- Plates: `python3 scripts/gen_image.py --model nb2 --size 1K --aspect 4:5 --ref <B>/brand/packs/pack-<sku>.png ...`
  (pull refs with `asset_library.py refs`). 1K for exploration, **15 or fewer per shot**; print
  the cost before generating. **The winner is re-generated at 4K** (`--model pro --size 4K`, the 1K
  pick as an extra `--ref` for composition) BEFORE repair and the print gate. 2K is not enough:
  a 2K 4:5 plate is about 1664 wide, under the floor below. Frame 4:5 with a clean top third; if
  the plate also runs 9:16, brief a separate 9:16 plate with headroom above the product instead
  of stretching the 4:5.
- **Resolution floor for anything that ships:** a plate in an ad must be at least 2x the Figma
  frame: **2160 wide for 4:5, 3840 tall for 9:16.** A 1K plate in a 1080 frame looks fine on
  the canvas and grainy on a phone next to sharp vector type. Enforced:
  `scripts/qa_export.py --plates <png...>`.
- **Every generated plate with the pack in it goes through the print gate before use:**
  `python3 scripts/print_gate.py --brand <brand> --plates <png> --out <dir>` (or
  `asset_library.py gate <brand> <id> --print`) must return `wrong=0`. If not, repair with
  `scripts/label_composite.py` (below), gate again, and only then upload.
- Generated people and hands: fine for planning and examples. Anything that SHIPS follows the
  brand's own rule (many brands require sign-off for AI-generated people).

### BATCH (a deliverables page, about 4-10 calls)
1. Read the test queue on the Roadmap; pick 2-3 ads. Write the brief: angle, template, headline
   from the gated copy file, traits, hypothesis, budget, keep and kill lines.
2. One `use_figma`: create `B<nn> · mm/dd · <name>`; a cover frame (test cards, read rule, VERIFY
   list); every ad as an **instance** of a template in both ratios, properties set, never detached.
3. Export each ad with `download_assets`, png, **scale 2** (2160x2700 and 2160x3840), to
   `<B>/runs/b<nn>/`. Meta builds the phone derivative from what you upload, so a 1080-wide upload
   is upscaled on every phone. A 2x export is only sharp when the plate under it meets the floor.
   A file under 800 KB means an image fill had not landed: wait a minute, export again.
4. QA gate (section 5). Fix in the template when a defect is structural, so every future ad
   inherits the fix.
5. Record the batch in `state.json.batches` (page id, instance ids, budget, keep and kill lines,
   `ad_name_tag`). Make the contact sheet (`scripts/sheet.py <B>/runs/b<nn> <B>/runs/b<nn>/sheet.jpg`)
   and hand over the PNGs, the sheet and the Figma link.

### REVIEW (someone edited or commented)
Read comments (step 0.2). Map each to its node. Fix in the template if it is a rule, on the
instance if it is a one-off. Re-export only what changed. Reply to each comment with what changed.
Rules that come out of a comment go into `copy-rules.json`, the template, or `state.json.lessons`
the same turn.

### EXPORT FOR LAUNCH (the person uploads)
This skill never writes to an ad account. Hand over, per ad: the 4:5 for feed and the 9:16 for
Stories/Reels (one ad carrying both, using Meta's per-placement asset customisation), the
primary text and headline from the copy file, and the ad name with its batch tag
(`<brand>-B01-A-<sub-angle>`). Recommend launching new ads PAUSED for a final check in Ads
Manager. Once they run, set `state.json.batches.<id>.launched = true` so LEARN reads the test.

### SYNC (disk to Figma, in place)
- Roadmap: `python3 scripts/sync_payload.py <brand>` prints the payload; one `use_figma` updates
  each sub-angle row's chips and spend line in place (rows found by name = sub-angle id).
- Learnings: `sync_payload.py <brand> --learnings`, the same way for the trait cards.
- Never rebuild a page a person has touched. Never delete a frame to redraw it.

## 4. Doctrine

1. **Every layer separate and editable.** Text on text layers, labels and badges as components,
   the pack as a real photo cutout, only the background plate generated. Edits happen in the
   right panel (component properties), never by detaching.
2. **Fonts close to the site, from Figma's library.** Exports come straight from Figma.
3. **Labels on every ad.** Label wording comes from the truth ledger; a claim with no verified
   row renders with a VERIFY flag on the batch cover.
4. **Claims compliance is not waivable.** Every line passes the copy gate; the hedge is the
   load-bearing word.
5. **Be stingy with Figma calls** (section 0.3).
6. **The file is the shelf; it compounds.** A verdict becomes a constraint in a component or a
   template badge, not a sentence in a doc. A losing template is demoted (badge: SUPPORT ONLY)
   or deleted. Structural fixes go into the template, so every later ad inherits them.
7. **A generated pack is never trusted.** The pack is the real photograph, or a plate that passed
   the print gate letter-perfect. Fluent garble is worse than mush, and a generated pack invents
   claims.

## 5. Batch QA gate (all of it, every batch)

1. `python3 scripts/qa_export.py <png> --plates <plate png...> [--contrast x0,y0,x1,y1[:dark]]` on
   every export: exact 2x size, file over 800 KB, every plate at or above the floor, flat
   backgrounds measured for margins and safe zones (9:16 top 250 / bottom 240, 1x units), photo
   backgrounds flagged NEEDS EYES, small text over a photo at 4.5:1 contrast or better.
2. Figma `check()` passed in the build call (no overflow, no collapsed text; no capital-S decade
   if the brand turned the optional decade rule on).
3. The print gate passed on every generated plate in the batch (`wrong=0`).
4. **Open every final at full size, and count them** ("6 of 6 viewed"). Look for: text on the
   product, a line touching the pack's top edge (9:16 crops), stickers near the edge (rotated
   items: position by render bounds), the disclaimer readable, anything broken, warped or artifacted (design law 29).
5. The copy gate passed on the copy file the batch used.
6. The judge gate in `reference/design-laws.md` section F, next to 3+ reference ads.
7. VERIFY list on the cover: offer terms, any ledger row still `candidate`, AI people or hands,
   anything on the pack's own print that clashes with the brand's rules. A gate failed on purpose
   is written on the cover with its reason.
8. Write `<B>/runs/b<nn>/qa.json`.

## 6. Scripts (`scripts/`, all zero Figma calls)

| script | what it does |
|---|---|
| `init_brand.py <brand> --name ..` | scaffolds `$AD_LIBRARY_HOME/<brand>/` from `templates/brand/` |
| `crawl_site.py <brand> --site ..` | the brand's own site photography at full resolution |
| `cutout.py <brand> <photo> --name ..` | transparent pack cutout from a plain-background photo |
| `asset_library.py ...` | the Library registry: approved refs only, sha-locked, print-gated products |
| `ref_sheet.py --brand .. --type ..` | product / location / character reference sheets into the Library |
| `gen_image.py ...` | one plate on Gemini (nb2 or pro, 1K/2K/4K, real pack as `--ref`) |
| `print_gate.py ...` | letter-perfect print gate on generated plates (Gemini vision transcribes, a scorer decides) |
| `label_composite.py <plate> <pack> <out> <fit.json>` | real-label repair: spline warp fitted to SIFT matches + anchors + per-cell patches, relit from the plate, with occlusion. Needs `requirements-repair.txt` |
| `copy_gate.py <brand> <copy.json>` | claims vs ledger, byte-exact quotes, bans, hedges, required fields, optional decade rule |
| `learn.py <brand> [--no-meta]` | Meta pull, angle-tree re-map keeping verdicts, batch reads, refresh note |
| `sync_payload.py <brand> [--learnings]` | the Roadmap / Learnings SYNC payload |
| `qa_export.py <png> ...` | export QA: 2x size, file size, plate floor, geometry, contrast |
| `sheet.py <dir> <out.jpg> [cols]` | contact sheet of a batch's exports |
| `figma_comments.py list/pending/reply` | read and answer Figma comments (REST, `FIGMA_TOKEN`) |
| `probe_gemini.py` | proves the Gemini key with a real (free) call |
| `selftest.py` | offline test of every offline-testable script (it lists what it does not cover) |

`examples/example-state.json` shows the state shape after ONBOARD and one batch, for a made-up brand.

## 7. Known traps (each one cost time)

- `download_assets` right after an upload can export without the image (a tiny file). Check the
  size, retry a minute later.
- Text: `resize()` after `textAutoResize = "HEIGHT"` locks the height at 10px. NONE, resize, HEIGHT.
- A null `t.name` rolls back the whole call: `t.name = prop || "label"`.
- A HORIZONTAL row clips when its counter axis is fixed: resize, then `counterAxisSizingMode = "AUTO"`.
- Component properties: add them on each variant before `combineAsVariants`; read keys by name prefix.
- `get_screenshot` on very tall frames can ghost text; re-shoot the section before calling it a defect.
- Swapping a photo through an INSTANCE_SWAP property resets the nested instance to the new
  component's native size, leaving a grey band. Author every photo component at its slot size
  (4x5 1088x1350, 9x16 1080x1935) with the image rect on FILL. The slot size is in Figma points:
  the image behind the fill still has to be 2x those points or the 2x export is soft.
- An INSTANCE_SWAP property has one default for the whole set. When each ratio needs its own
  photo, give the 9x16 its own property ("Photo 9x16").
- Grain copied from a plate's high-pass carries garbled letters' edges back in: the repair clips
  it to ±4 levels (and uses none in small cells).
- The label repair's "face" mode paints the real print over everything in front of the pack.
  Food or props the same colour as the label defeat the automatic occlusion check; draw
  `occluders` polygons in the fit file and look at the edge at full size before the print gate.
- A fill-less frame exports on opaque grey, not transparent.
- The print gate can read unresolvable fine print (a net-weight box at about 3pt on a phone) as a
  confident wrong string. If the pixels ARE the real pack's print and the read is "soft", log a
  documented exception with the measured size on the batch cover; never blur it to pass.
- A Meta pull through an MCP tool can cap at 1,000 ads. `learn.py` reads every ad
  with spend through Graph insights `level=ad`, `date_preset=maximum`, paged.

## Off-switch

Delete this skill's folder. The Figma files and `$AD_LIBRARY_HOME/<brand>/` folders stay as data.
Revoke the Meta and Figma tokens you created if you no longer need them.
