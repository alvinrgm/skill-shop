# loop-engine — the canonical ad-QA instruments

The measurement half of the ad loop. This is the ONE place the algorithms live. The
thresholds were calibrated in a prior run; the artifacts they were calibrated on are not
shipped, so `selftest.py` proves each instrument on synthetic inputs instead, in both
directions: it passes a clean artifact and fails a broken one.

Nothing in here is client-specific. Every path and credential resolves through
`../config.py`. The client layer supplies data (the reference pack shot, the pack's real
printed strings, the review records, the design tokens), never code.

```
python3 selftest.py            # every module on synthetic artifacts, no API calls
python3 selftest.py --live     # plus one real Gemini vision call
```

---

## The instruments

| Instrument | What it measures | How to call |
|---|---|---|
| `common.lum / srgb_lin / rel_lum / contrast / hex2rgb` | Rec.709 luminance and WCAG contrast primitives | `common.contrast(fg_rgb, bg_rgb)` |
| `common.dilate` | box dilation by cumulative sums (no scipy dependency; the workaround is deliberate) | `common.dilate(mask, kx, ky)` |
| `common.components` | two-pass run-length connected components, 8-connected | `labels, ids = common.components(mask)` |
| `common.row_bands / bands` | row-profile segmentation into line bands | `common.row_bands(rows_any, min_h=1)` |
| `common.boxblur / red_mask` | separable box blur; the saturated-brand-band mask that separates a red band from warm-brown surfaces by R−G, not saturation | `common.red_mask(rgb, loose=False)` |
| `zones.ZoneQA.find_blocks` | measured type blocks + per-block line bands, from the render's own ink | `q.find_blocks()` |
| `zones.ZoneQA.margins` | outer margins + the 4:5 bottom safe zone, from the measured ink bbox | `q.margins()` |
| `zones.ZoneQA.fold_and_headline` | fold band, ink above it, and headline x-height vs law 4's 10–14% as a **hard gate** | `q.fold_and_headline(anchor={"accent": "<accent hex>", "max_y":360, "max_x":700})` |
| `zones.ZoneQA.block_collisions` | pairwise overlap of merged blocks at an 8px gutter | `q.block_collisions()` |
| `zones.ZoneQA.element_collisions` | DOM element boxes cross-checked against pixels, grouped to the logical element | `q.element_collisions(elements)` |
| `zones.ZoneQA.photo_collisions` | type-vs-photograph overlap and gutter, against the photo's **alpha**, not its box | `q.photo_collisions()` |
| `zones.ZoneQA.wcag_lines` | WCAG per LINE against its own size threshold | `q.wcag_lines()` |
| `zones.ZoneQA.wcag_elements` | WCAG per DECLARED ELEMENT on its own **exclusive** ink | `q.wcag_elements(elements)` |
| `zones.ZoneQA.wcag_blocks_vs_plate` | plate mode: ink vs the worst ground the glyphs actually cover | `q.wcag_blocks_vs_plate()` |
| `zones.ZoneQA.flatness_halo` | law 21, ink-halo cell form — the ground a reader sees behind the glyphs | `q.flatness_halo()` |
| `zones.ZoneQA.flatness_field` | law 21, whole-canvas background range on a declared flat field | `q.flatness_field()` |
| `zones.ZoneQA.lit_ground` | no ink over anything lit (the L-over-fingertip defect, mechanised) | `q.lit_ground()` |
| `zones.ZoneQA.never_enlarge` | law 29: an asset may be downsampled, never enlarged | `q.never_enlarge([("logo", <native_w>, <rendered_w>)])` |
| `zones.ZoneQA.accent_discipline` | one accent used as one system; type-family count | `q.accent_discipline(accent, ink, families=..., expect_families=2)` |
| `zones.ZoneQA.pack_print` | rendered cap-height of the print ON a photographed package | `q.pack_print(spec, ratio, at, plate_size)` |
| `physics.filter_a` | row-luminance SD floor — kills mathematically flat fields | `physics.filter_a(rgb, bag)` |
| `physics.filter_b` | shadow probe: contact ratio, seam depth, monotonic recovery, **signed** centroid throw | `physics.filter_b(rgb, bag)` |
| `physics.b_direction_ok` | throw direction agrees with the **measured** lateral gradient (never the prompt's) | `physics.b_direction_ok(B, bag, A)` |
| `physics.filter_c` | hue preservation in the umbra — an achromatic umbra is the composited tell | `physics.filter_c(rgb, bag)` |
| `physics.filter_d` | downsample vs the real reference object + high-pass detail energy in its printed band | `physics.filter_d(rgb, bag, ref_pack)` |
| `physics.locate_bag` | geometry from a vision `boxes.json`, refined to the seam by pixels | `physics.locate_bag(rgb, name, boxes)` |
| `physics.renormalise_box` | re-normalise a vision box for a delivered CROP so the cascade can be re-run on it | `physics.renormalise_box(box, <src_w>, <crop_w>)` |
| `triage.run` | the cascade over a batch: locate → A → B → C → D, per-plate table, `triage.json`, survival curve | `python3 triage.py --plates '…/*.png' --boxes boxes.json --ref REAL.png` |
| `vision.localise` | object box, printed-band box, contact line, light direction | `python3 vision.py localise --plates … --out boxes.json --subject "<your pack>"` |
| `vision.inspect` | 4x forensics: surface texture, label-on-curvature, displacement, duplication, single-light | `python3 vision.py inspect --plates … --out QA/` |
| `vision.print_filter` + `score_print` | the letter-perfect filter — **the model transcribes, the script decides** | `python3 vision.py print --plates … --client <slug> --out QA/` |
| `vision.judge_view` | downsample to the delivery canvas, then magnify — the honest test of what ships | `vision.judge_view(plate, zoom=3)` |
| `vision.gi_filter` | global illumination: one key? every object casting? orphan shadows / inpaint arcs? | `python3 vision.py gi --plates … --out QA/` |
| `device.invariant_column` / `report_column` | the concept's DEVICE measured as the device: one size, one x, one pitch, right count | `device.invariant_column(png, field, accent, y0, y1, x1, n_expected=6)` |
| `claims.verify` | whole-unit quote verification, verified flag, rating, author, year, word cap, invariant, **product line**, batch byte-match | `python3 claims.py SPEC.json` (`--print-example` for the shape) |
| `glance.build` | 1.5s-glance blur, 180px thumb, 378px phone, measured-box overlay, cap-height arithmetic | `glance.build(render, out_dir, blocks=…, fold=…, safe=…, declared_type=[…])` |

---

## Honesty notes that travel with specific instruments

**An instrument that counts a photographed object's own print as the ad's text will fail
every product photograph.** A text-recall check can fail an ad because most of the "lost"
strings were the *pack's* printed lines, not the ad's type. **Report it, do not move the
bar.** The fix belongs upstream in the instrument and must be validated against the
corpus, never against the ad that exposed it. `zones.pack_print` exists precisely to measure the pack's own print
*separately* from the type layer, so the two never get scored as one thing.

**Instruments port with documented sampling changes only; thresholds never move
mid-experiment.** Every generalisation made when these were consolidated into one module
carries a comment at the line where it happens. The full list:

- `physics.filter_d` takes `ref_pack` as an argument (was a client module constant).
- `physics.locate_bag` takes `boxes` as an argument (was a module global read off disk),
  so a crop can be probed with a re-normalised box without mutating module state.
- `physics.DARK_SIDE_DEFAULT` is a caller-supplied map; a variant absent from it yields
  `prompt_light_ok=None` instead of a `KeyError`. It is **recorded, never gated** — the
  gate is `b_direction_ok`, which reads the measured lateral gradient.
- `physics.analyse` keeps `occluded` / `in_frame` boolean in the JSON instead of coercing
  them to 0/1. No gate reads either field.
- `common.row_bands` takes `min_h` explicitly (the zone QA uses 1, the device instrument 2).
- `zones` defaults to an ink threshold of 26 (channel sum). A looser band-differencing
  variant used `mean(2) > 22` ≡ sum 66; pass `ink_delta=66` to reproduce it exactly.
- `zones.never_enlarge` normalises two inverted expressions of law 29 into one
  (`enlargement = rendered / native`, fail > 1.0) and reports the downsample alongside.
- `vision`'s TRUTH list moved out of the module into `<brand>/pack-strings.json` (see
  below). `LOCALISE` takes the subject as `--subject`; `INSPECT` uses generic nouns
  (pass `prompt=` to specialise it).
- `claims`' category flag is `OFF-CATEGORY-SKU`, driven by a spec regex.
- `glance` computes the phone height by truncation (472, where rounding gives 473 —
  a one-pixel difference, not a threshold).

**A sharpened instrument must re-fail the artifact it was written for.** If
you sharpen anything here, point it at the file that exposed the gap and show it failing
there. `selftest.py` asserts the constants are unmoved and that every instrument both
passes a clean synthetic artifact and fails a broken one.

**No zone is ever hand-typed.** `ZoneQA` takes images and finds the ink
itself. The only declared inputs that remain are semantic (which colour is the accent,
where the anchor search window is, which y-band a pack's printed line lands in) and they
are labelled DECLARED wherever they appear.

**A pixel-only collision test goes quiet exactly when it should shout.** Run
`element_collisions` alongside `block_collisions` whenever a DOM probe exists; every
declared box is also checked to carry ink, so the DOM cannot lie either.

**Filters A and C almost never kill a single render.** Composite-era checks stay
for composites; single-render triage weight goes to B (shadow behaviour) and D
(micro-detail). Do not read a clean A/C on a single render as evidence of anything.

**A batch returning zero survivors is a result** when the filters that killed
it are new and validated. Report the curve; do not lower a filter that was written this
morning to justify the plates generated this afternoon.

---

## The client layer

Nothing here hardcodes a client. Three data files are read from `config.brand_dir(slug)`:

| File | Read by | Contents |
|---|---|---|
| `pack-reference.txt` | `physics.ref_pack_for(slug)` | one line: path to the **real photograph** of the object filter D calibrates against. Deliberately no filename heuristic — a heuristic would silently calibrate against the wrong object and every downsample number after it would be wrong but plausible. |
| `pack-strings.json` | `vision.load_truth(slug=…)` | `{"strings": [...]}` — the pack's real printed lines. Without it `score_print` treats every transcribed string as a fabrication, so `load_truth` warns loudly rather than returning `[]` quietly. Falls back to `fixtures/<slug>-pack-strings.json`. |
| a claims spec JSON | `claims.main` | review record globs, schema, SKU in frame, product-line regex, the shipped fragments. `python3 claims.py --print-example` prints the shape. |

`fixtures/example-pack-strings.json` ships as the format example and as the selftest's
truth list; a client's canonical copy belongs in its brand folder, not here.

**Filter D's band detector** (`common.red_mask`) looks for a saturated warm/red printed
band, because that is what the pack it was calibrated on carried. If your pack's label
band is another colour, point the localiser at it with `--subject` and expect filter D to
need a matching mask; report it rather than loosening `HP_RATIO_MIN`.

## Dependencies

Python 3, **numpy + Pillow only**. No scipy (the morphology workarounds are deliberate),
no `python-dotenv` (`config.py` parses the package `.env` itself).
