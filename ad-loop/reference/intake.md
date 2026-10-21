# intake — what a client layer is made of, and where each piece comes from

Companion to `scripts/intake.py`. Read this before running intake on a new client, and again
when intake returns a [GAP] you were hoping it would fill.

```
python3 scripts/intake.py --url https://brand.example --slug brand   # from the package folder
```

Everything resolves through `config.py`. Intake never hardcodes a path or a key.

---

## the one rule

**Anything that could not be harvested is written down as a `[GAP]`, never invented.**

A [GAP] is a research to-do, not a blank to fill in with imagination. This matters more here than
anywhere else in the loop, because intake runs at the moment when nobody knows anything about the
client yet — which is exactly when a plausible invention is impossible to catch and gets inherited
by every build downstream.

Intake also **never overwrites an existing file**. If a target exists it is left alone and the
report says so. Re-running intake on a live client layer is safe by construction.

---

## what intake harvests, and why each thing is load-bearing

| harvested | written to | why the loop needs it |
|---|---|---|
| platform + canonical domain | `INTAKE-REPORT.md` | decides which extraction path is even available |
| full product/image index | `brand/product-images/INDEX.md` | the complete asset inventory; also the volume engine's input |
| pack shots at **native resolution** | `brand/product-images/` | native width decides the ad's scale class before layout exists |
| logo candidates | `brand/logo-candidate-*` | the mark ships at full scale in nearly every ad |
| palette **candidates** with counts | `brand/palette-CANDIDATES.md` | tokens must be measured, never eyeballed |
| font families + files | `brand/fonts/` + `INDEX.md` | the type layer's raw material and its licensing question |
| review corpus, raw + summarised | `brand/reviews/` | the only source of the buyer's own words |
| claim **candidates** + sources | `brand/claims-CANDIDATES.md` | the legal surface, staged for human approval |
| Ad Library page ids + next command | `brand/adlib-pages.md` | competitor/North-Star harvest can't start without them |
| honest [GAP] stubs | `brand/*.md`, `personas/*` | makes the loop fail loudly instead of proceeding blind |

### native resolution is not a detail

Three learnings collapse into one number. With `s` = the pack's delivery downsample against the
native file:

- Micro-print stops reading at roughly **`s = 2.9`**, and every quantity that matters scales as
  `k/s` — micro-strip cap, headline-band cap, pack width. One knob, one division.
- **A plate's maximum `s` is its full-frame value.** Cropping only ever lowers it. So scale class
  is decidable in two minutes, before any layout, and it can eliminate a finalist plate outright.
- Downsampling real detail past legibility **reads as AI garble** to a judge. Authenticity is not
  inherited from the source file; it is re-earned at render scale.

`product-images/INDEX.md` therefore carries, per file: native px, the `s=2.9` delivery cap in
pixels, and that cap as a share of a 1080 canvas against law 2's 40-70% product coverage. A pack
shot whose native width can't reach the band has a ceiling, and the honest move is to name the
ceiling — not to shrink the concept until a picture fits.

The **alpha** column exists for the same reason at a different scale: a soft matte and a hard
lasso cut are different assets. A cutout is detected by physics, not edges.

---

## platform detection

| platform | signal intake looks for | complete image index? |
|---|---|---|
| **Shopify** | `/products.json` responds with a `products` key; or `Shopify.shop` / `cdn/shop/` / `myshopify.com` in the HTML | **yes** — `/products.json?limit=250&page=N` |
| WooCommerce | `woocommerce` / `wp-content/plugins/woo` | no — falls back to the per-page cascade |
| BigCommerce | `bigcommerce.com` / `stencil-utils` | no |
| Squarespace | `squarespace.com` / `Static.SQUARESPACE` | no |
| Wix | `wixstatic.com` | no |
| Webflow | `webflow.com` / `w-webflow` | no |
| anything else | — | no |

**Non-Shopify sites fall back to `runtime/gen/pdp_scrape.py`'s cascade**, which
intake imports rather than reimplements: Shopify product JSON → JSON-LD → OpenGraph →
`<img>` src/srcset with icons filtered. That cascade is per-page, so a non-Shopify client needs
intake run per PDP, or images dropped in by hand. When it yields nothing, `pdp_scrape.py` exits
nonzero on purpose so the gate trips — do not let anything downstream invent the package.

### storefront CDN quirks (hard-won, do not re-discover)

- **`?v=…` and `?width=…` are cache/resize params.** Strip the query string to fetch the master.
- **`_NNNx`, `_NNNxNNN`, `_grande`, `_large`, `_medium`, `_master` in the PATH are downsamples.**
  Strip those suffixes — *except* on URLs that came from `products.json`, whose `src` values are
  already originals. Intake tracks this with a `trusted` flag per image.
- **`products.json` reports true `width`/`height` per image.** Intake downloads the file and
  measures it anyway, and reports a mismatch: a mismatch means a downsample was served, not the
  master, and the whole `s` arithmetic above would have been wrong.
- **The storefront serves from `<domain>/cdn/shop/…`, not necessarily `cdn.shopify.com`.**
  Grepping page HTML for `cdn.shopify.com` can return only UI icons and miss every photograph.
- **Filenames lie.** Verify visually what a file contains: a run of files named
  `...lifestyle_N` can show a different product from the one they are attached to.
- **Sequence-probe promising filenames.** Unlinked frames from a shoot often stay served.
  Probing `-02..-10` on a filename referenced only at `-01` and `-07` can surface more frames,
  sometimes including the best asset available. Intake does not do this; a human should.

---

## palette and fonts: measured, never eyeballed

Intake reads the homepage's `<style>` blocks plus up to eight linked stylesheets, counts every
literal hex, and maps hexes back to their CSS custom-property names. The output is
`palette-CANDIDATES.md` **with the counts shown**, so a human can see why each value is on the
list and overrule it.

Frequency finds the theme's working colours, not the brand's intent. A hex used 600 times is
usually a UI grey; a brand's real accent can appear twice. **Intake never picks tokens.**

Fonts: `@font-face` families/weights/styles plus any Google Fonts links, with the binaries
downloaded where the CDN permits. Two things intake cannot resolve and flags as [GAP]s:

- **Licensing.** A webfont served to a browser is not a licence to render paid advertising.
- **The display face.** The theme's webfont is frequently not the brand's display typeface. That
  lives in the brand book.

---

## review-platform detection

Reviews are the highest-value harvest in the whole run — they are the only place the buyer's own
words exist. Intake detects five platforms and implements three.

### detection is TWO-TIER, and that matters

A bare substring match is **not** evidence. A modern Shopify theme ships one analytics snippet
that names every review platform it could integrate with, all set to null:

```js
var MetafieldYotpoRating = null; var MetafieldLooxRating = null; var okendoProduct = null;
```

So a substring scan reports three platforms on a store running none of them. (A vendor name
can appear many times in a PDP and every occurrence be that boilerplate. "Detected, key not
found" is then a false positive, and a false positive here sends a human hunting for a key
that never existed.)

- **STRONG** — a request actually goes to the vendor, or its widget element is present. Detected.
- **WEAK only** — the name merely appears. Reported as *"named in the page source, no live
  signal"* and **never** treated as detected.
- A key found in the HTML counts as strong on its own.

| platform | STRONG marker | public key pattern | status |
|---|---|---|---|
| **Stamped** | `stamped.io`, `stamped-widget`, `data-widget-type=…stamped` | `pubkey-…` | **IMPLEMENTED** |
| **Yotpo** | `staticw2.yotpo.com`, `api[-cdn].yotpo.com`, `yotpo-widget-instance`, `data-yotpo-instance-id` | `staticw2.yotpo.com/<key>/widget.js` (40 alphanumeric chars — **not** 32 hex), else `appkey` / `app_key` | **IMPLEMENTED** |
| **Okendo** | `okendo.io`, `<oke-`, `oke-w-`, `data-oke-*` | `<meta name="oke:subscriber_id" content="<uuid>">`, else `subscriberId` | **IMPLEMENTED** |
| Judge.me | `judge.me/`, `jdgm-widget`, `data-shop-token` | `shop_token` / `data-shop-token` | detected only |
| Loox | `loox.io`, `loox-reviews`, `data-loox` | shop identifier | detected only |

Records from every platform are **normalised onto the Stamped field names** so one schema serves
every downstream consumer (`SUMMARY.md`, `loop-engine/claims.py`). The raw pages keep each
vendor's own field names and are saved verbatim as `raw-<platform>-*.json`. **Byte-match a quote
against the RAW file, never against the normalised summary table.**

### the Stamped path (fully documented)

The **public widget key** is printed in the served PDP HTML. It is not a secret — it is what the
browser uses to render the review widget. With it:

```
GET https://stamped.io/api/widget/reviews?storeUrl=<domain>&apiKey=pubkey-XXXXXXXX&take=100&page=N
```

returns full review records: `id`, `author`, `reviewTitle`, `reviewMessage`, `reviewRating`,
`reviewDate`, `reviewVerifiedType`, `productName`, `productSKU`. Intake saves every page verbatim
as `brand/reviews/raw-p*.json` — the raw files are the evidence, `SUMMARY.md` is derived.

**The critical caveat, and it is not small: the public API has been observed to expose only
5-star reviews.** On an audited store that meant thousands of five-star records and none at
1-4 stars. So a persona built on this corpus has **no objections in it** and will systematically
flatter whatever it is shown. The single highest-value refresh for any client is a **full export
from inside the client's review account, including low-rated reviews.** Intake prints this warning
into `SUMMARY.md` every time.

`SUMMARY.md` derives two lists:

- **persona seed material** — 3-and-4-word phrases recurring across four or more *distinct*
  reviews, each with example record ids. These are threads to pull, not personas. Open the cited
  records and read them whole.
- **verdict-quote candidates** — verified, 5-star, and a **whole unit under ten words**, so nothing
  has to be elided. Each carries record id, author, date, **product line** and SKU.

Three rules govern anything that leaves that list:

1. **Verify the PRODUCT LINE, not only the text, rating and verified flag.** A glowing review
   filed against an accessory is not evidence for the product in frame.
2. **Elision is a compliance surface, not a style choice** (FTC 16 CFR 255.1). Elide only whole
   trailing content, never an internal qualifier — dropping a reviewer's own uncertainty
   materially changes meaning. Prefer quotes that need no elision at all.
3. **Attribution framing is itself a claims surface.** An eyebrow like "from the reviews" may
   cover only byte-verified quoted material; brand-voiced lines live outside the attributed block.

Whatever ships must **byte-match** the raw record, and the match must be written into a provenance
file beside the ad.

### the Yotpo path (live-verified in a prior run)

```
GET https://api-cdn.yotpo.com/v1/widget/<appkey>/products/<shopify_product_id>/reviews.json
    ?per_page=150&page=N
```

GET only, no auth header (the docs claim a required `X-Yotpo-Token`; empirically false — a
no-header GET returns 200). Records live at `response.reviews[]`. Fields: `content`, `title`,
`score`, `created_at`, `verified_buyer`, `user.display_name`, `id`.

Four things that are easy to get wrong:

1. **There is NO public all-reviews endpoint.** `/v1/apps/<key>/reviews` is the authenticated
   admin API and returns 401. `yotpo_site_reviews` is a real path but holds only *store-level*
   reviews (a virtual product), not every product's. Full coverage is a **per-product fan-out**
   over the Shopify ids intake already indexed, bounded by `--yotpo-products` (default 25) — and
   the bound is printed as a [GAP] rather than pretended away.
2. **The review object carries no product NAME.** It is in the envelope at
   `response.products[0].name` and must be joined, or every record files against
   `[GAP] unnamed` and the product-line verification rule cannot run.
3. **The loader GUID is not the app key.** A page carrying
   `cdn-widgetsrepository.yotpo.com/v1/loader/<GUID>` also carries a *different* Loyalty/Widget-3.0
   id that **404s** against the reviews API. Take the key from `staticw2.yotpo.com/<key>/widget.js`.
   A wrong key returns **404, not 401**.
4. `per_page` **hard-caps at 150** (asking for more is silently clamped); CDN data runs ~3h behind.

### the Okendo path (live-verified in a prior run)

```
GET https://api.okendo.io/v1/stores/<subscriberId>/reviews?limit=100&orderBy=date%20desc
```

**The best of the three.** Store-wide — no product id needed — and it returns ratings 1-5, so
unlike Stamped it carries the objections. Records at top-level `reviews[]`. Fields: `body`,
`title`, `rating`, `reviewer.displayName`, `reviewer.isVerified`, `dateCreated`, `productName`,
`reviewId`, `status`.

- **Cursor pagination, not offset.** Follow `nextUrl`, which comes back as a **path** and must be
  joined onto `https://api.okendo.io/v1`. Its absence means stop.
- `limit` caps at **100** (the docs say 25 — stale).
- **An unknown store id returns 200 with `{"reviews":[]}`**, never an error. So an empty result is
  reported as *"answered empty, the id may be wrong"* — it is not evidence the store has no reviews.
- `reviewer.isVerified` is **absent entirely** when false; read it defensively.
- Only `status: "approved"` is exposed. Moderation-pending and rejected reviews are invisible.
- Syndicated reviews from other stores appear (`syndicatedFromSubscriberId`) — filter if you want
  first-party only.

### the two still-unimplemented platforms

Each has a public read path. If you build one, extend the `REVIEW_PLATFORMS` table and add a
harvester alongside the others in `intake.py` — never write a second harvester script.

- **Judge.me** — `judge.me/api/v1/reviews?shop_domain=<domain>&api_token=…` needs a private token;
  the public widget path is `judge.me/reviews/reviews_for_widget` with the shop token from the HTML.
- **Loox** — widget-rendered; find the JSON request in a PDP's network tab once and the URL shape
  is stable.

For both, the honest interim move is what intake already does: **detect it, print the key it
found, and mark it unimplemented** so a human knows exactly which door to open next.

### and the caveat that survives ALL of them

Every public widget API hides a different slice and none of them says so: Stamped's exposes only
5-star records, Okendo's only `approved` ones, Yotpo has no all-reviews endpoint at all. Even a
fully successful harvest is a positive-skewed sample. **The single highest-value refresh for any
client is still a full export from inside their own review account, including 1-4 star reviews.**

---

## Meta Ad Library page ids

Two methods, and the ranking matters.

**1. Recovery from a known `ad_archive_id` — DEFINITIVE.** Open

```
https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=US&id=<AD_ARCHIVE_ID>
```

and read the owning page off the ad itself. This does not guess: it reads which page an ad you
already have actually ran from. Pass it as `--library-id "<slug>|<ad_archive_id>"`. Library ids
are recorded in every `harvest_inspo.py` manifest, so a re-resolve is usually free.

**2. Public keyword search — good, sometimes defeated.**
`?q=<brand>&search_type=keyword_unordered`, tally page ids across the results, score by name
match. **Retailers reliably drown out the brand** for anything sold through third parties — one
documented case returned NOT FOUND for the brand by keyword and had to be recovered from library
ids twice.

**Do not reach for the advertiser typeahead.** `/ads/library/async/search_typeahead/` sits behind
a bot-verification challenge — not a login wall, but **unusable headless**. This is a
finding, not a task.

Both methods need Playwright. **Playwright's absence is not a crash** — intake writes
`brand/adlib-pages.md` with the manual browser steps and the harvest commands with `<PAGE_ID>`
left as a placeholder.

### harvesting after resolution

`brand/adlib-pages.md` ends with the exact command lines. Two settled facts baked into them:

- **`--media all`, always.** Meta's server-side `media_type=image` filter is unreliable — it has
  returned "No ads" for pages demonstrably running statics. `--media all` still yields only real
  statics because the extractor reads `snapshot.images[]`/`cards[]` and never
  `video_preview_image_url`.
- **The harvester dedupes by content (md5 + dhash), not filename.** A re-uploaded creative gets a
  fresh CDN filename, so filename identity alone inflates a corpus. Signed CDN URLs expire in
  about five days, which is why it downloads immediately.

An empty result for an `active_status=active` query can be a **real finding** (creative rotation),
not a failure.

---

## claims: candidates only, forever

Intake extracts bullet points, spec lines, certification words and numerals from PDP bodies and
homepage meta, and writes them to `claims-CANDIDATES.md` with each candidate's **verbatim source
string** and **source URL**. Every row is marked `[NEEDS HUMAN APPROVAL]`.

**Intake never writes an approved-claims file with content.** `brand/approved-claims.md` is
scaffolded empty, pointing at the candidates. An approved claim is a human's signature on a
substantiated statement, and the file's whole value is that it cannot have been forged.

Two rules that survive every rewrite:

- **The hedge is the load-bearing word.** Every rewrite that "sounds better" usually got there by
  deleting the hedge — which converts an approved statement into an unapproved health claim.
- **The hedge never takes the headline.** It reads as the lawyer talking and manufactures the
  reader's objection: "many find" invites "many don't". The unique checkable fact leads; the
  hedged claim supports.

What is missing from the candidates list **by construction**: everything printed on the physical
package that web copy does not repeat; all substantiation; regulated-category and platform ad
rules; and whatever the client has already been told they cannot say. That last one is usually a
short list and it is never online — ask.

---

## what intake CANNOT get

Not "has not got yet". Cannot, by nature. Each of these is scaffolded as a [GAP] stub that says
what it is for and what is missing.

- **Art direction.** Intake can count hexes and name webfonts. It cannot decide a look. Automatic
  style/colour/font picking produces exactly the generic mean this loop exists to beat.
- **Brand tensions.** A tension surfaces in what a client says out loud, what low-star reviews
  complain about, and what the category refuses to admit. A fabricated tension is worse than
  none — it sends every build chasing a conflict nobody has.
- **North Star picks.** Hand-chosen by the operator, never harvested. A harvested corpus tells
  you what the category *does*; a North Star tells you what *good is*. Collapsing them is how a
  loop converges on the mean. The `why this one` line beside each pick is the actual asset.
- **Approved claims.** See above.
- **Personas.** Intake supplies seed material from one positive-skewed source. A persona is an
  evidence anthology with a grounding rule, not a writer's guess.
- **Anything behind a login** — the client's review export, their ad account, their search-term
  report, their brand book PDF, their raw photography. All of it is higher-value than anything
  intake can reach, and all of it is one ask away.
- **Reddit and most forums headless.** Blocked at every path tried. Needs a scoped-tab pass in a
  logged-in browser, interactively. Never headless.
- **Whether a photograph is real.** Provenance of publication is not a forensic guarantee. And
  the harder half: a genuinely real photo can still *read* as fake once cropped past its context.
  The gate question is never "is it real" but "does it read real at this size".

---

## manual-completion checklist (client is not loop-ready until every box is ticked)

- [ ] `brand/art-direction.md` — the look, tokens with roles, type behaviour, light and surface,
      the reference photograph, the always-wrong list.
- [ ] `brand/bible.md` — product line, who buys and who does not, voice, proof assets, the
      forbidden list, claim rules pointer.
- [ ] `brand/ad-creative-principles.md` — the client-specific layer on top of the global laws.
- [ ] `brand/tensions.md` — two or three real ones, each with the evidence that it is real.
- [ ] **At least one real persona** in `personas/`, built to the grounding rule, with a JUDGE
      PROTOCOL section. Get the client's full review export first.
- [ ] `brand/approved-claims.md` — populated by a human, byte-exact, with substantiation.
- [ ] `brand/north-star-picks/` — operator picks with a why-line each.
- [ ] **Pack shots verified**: which file is the hero, what each file actually contains, and each
      one's `s` ceiling read off `product-images/INDEX.md`.
- [ ] **Ad Library page ids confirmed** by opening them, then harvested.
- [ ] **Font licensing confirmed** for advertising use.

---

## flags

| flag | effect |
|---|---|
| `--url` | brand homepage **or** a PDP URL (a `/products/` path is detected and used for copy/review probing) |
| `--slug` | the client folder name under the work root (`AD_LOOP_HOME`) |
| `--root DIR` | overrides the work root (`AD_LOOP_HOME`) — **use this for smoke tests**, it is what keeps a test run out of a live client layer |
| `--max-images N` | cap on downloaded product images (default 40) |
| `--review-pages N` | Stamped pages at 100 records each (default 4) |
| `--competitor NAME` | repeatable; adds a name to Ad Library keyword resolution |
| `--library-id "slug\|id"` | repeatable; the definitive page-id method |
| `--country` | Ad Library country (default US) |
| `--skip STEP` | repeatable; one of `probe index images palette fonts reviews claims adlib skeleton` |
| `--dry-run` | fetch and report, write nothing |

**Exit codes:** `0` success, `2` a required step failed (site probe or product index) — so a
calling skill's gate trips instead of proceeding into a client layer with no product in it.

**Politeness:** one real User-Agent, sequential fetches with a short sleep, 30s timeouts, caps on
stylesheet count/size and download count. Intake is a guest on the client's storefront.
