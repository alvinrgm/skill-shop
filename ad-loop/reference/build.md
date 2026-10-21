# Build — how a winning concept + surviving plate becomes a finished static

The BUILD step of the loop (SKILL.md section 2, step 4). Read `design/design-laws.md`
first, every run: the laws are the shipping gate, not decoration. The bar: put the
finished ad next to your North Stars and it holds.

## The pieces (all shipped in this package)

| piece | path |
|---|---|
| Template kit + renderer | `runtime/static-kit/` (`node render.js <batch.json>`, `templates/`, `tokens.css`) |
| Contact sheet | `runtime/static-kit/tools/sheet.py <dir> <out.jpg> [cols]` |
| Inspo harvester | `runtime/static-kit/tools/harvest_inspo.py` -> `<work>/inspo/<advertiser>/` |
| Image generation (plates) | `runtime/gen/gen_image.py` (Gemini, your key; never a credit-billing image service) |
| Asset Library | `runtime/lib/asset_library.py` + `runtime/lib/ref_sheet.py` -> `<work>/<client>/library/` |
| Per-client output | `<work>/<client>/statics/loop-<concept>/{volume-NN,iter-NN}/{plates,finals,qa,batch.json}` |
| Client brand assets | `<work>/<client>/brand/` (bible.md, art-direction.md, ad-creative-principles.md, approved-claims.md, product-images/) |

Fonts: the brand's own licensed web fonts belong in `runtime/static-kit/fonts/` (see the
names `tokens.css` documents). The palette must be site-exact: intake samples the theme
CSS; never eyeball hex values.

## Pipeline

**0. Load context.** design-laws.md + the client layer (`brand/bible.md`,
`brand/art-direction.md`, `ad-creative-principles.md`, `approved-claims.md`). Every ad
line must trace to the approved list or carry `[NEEDS APPROVAL]`. Never invent offer
terms; flag unconfirmed ones to the operator.

**1. Angle.** One angle per ad, never blended. Proven winners from the account first (if
the operator shared any), then brand-lane angles from the harvested evidence.

**2. Concept card (the step that separates elite from template).** Before any pixels,
write one line each:
- *hook* (design-laws section E hook patterns: courage over safety)
- *archetype* (from the archetype menu in design-laws; vary across concepts)
- *device* (the ONE designed element dramatizing the claim: a week strip, a stamp, a stat
  trio, comic panels, an annotated diagram. No device = no ad.)
- *world* (single field colour / photo scene / illustration world)
- *image plan* (real cutout hero, generated scene, flat-lay, macro)

An ad missing any of the five gets rethought, not rendered.

**3. Plates.** From the volume batch's triage survivors only (SKILL.md section 2 steps
2-3). Product scenes always `--ref` the real pack shot from the Library
(`asset_library.py refs <client> <id>`). Image models mangle label small-print almost
always, so either the print passes the letter-perfect filter at delivery scale, or the
real cutout is composited over the generated pack (scale by HEIGHT, bottom-anchor, match
the scene's colour temperature) and the fixed plate is re-triaged.

**4. Copy + batch.json.** Claims from the approved list only, brand voice rules applied,
three text moments or fewer per ad. Run `runtime/scrub/scrub.py check` on the copy.

**5. Render.** `cd runtime/static-kit && node render.js <batch.json>`. 1080x1350 default;
1:1 and 9:16 variants only after the 4:5 is approved.

**6. Gate.** Never here: the five-instrument battery (SKILL.md section 3) judges the
render. The builder never judges its own build.

## Refreshing the inspo corpus

New category or a corpus older than ~90 days: get the advertiser's page id from the Ad
Library (search the advertiser at https://www.facebook.com/ads/library/, copy
`view_all_page_id=` from the URL, or use a Meta connector's Ad Library search), then

```bash
python3 runtime/static-kit/tools/harvest_inspo.py --page-id <id> --slug <advertiser> --media all --top 12
```

An advertiser returning 0 statics: suspect the TOOL first (Meta's `media_type=image`
filter has been unreliable; `--media all` is the default for that reason). A true zero is
still a finding, never a silent skip. Add per-advertiser notes and any NEW laws to
`design/design-laws.md`: the corpus teaches, the laws file accumulates.

## Hard rules

- Type is ALWAYS code-set in the kit. Never model-rendered text, never hand-placed in an
  image editor.
- The pack label is always the real photograph (law 8), or a generated plate whose print
  passed the letter-perfect filter at delivery scale.
- Images = gen_image.py on the Gemini key only.
- Per-client bible hard rules override everything here.
