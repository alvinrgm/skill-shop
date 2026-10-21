# static-kit: static ad rendering kit

Plain HTML/CSS type templates over real or generated imagery, rendered to PNG with
Playwright. No frameworks, no build step beyond `npm install`. This is the TYPE layer for
static ads. It never generates imagery itself.

## How it fits with the rest of ad-loop

- **Imagery** = real pack shots / lifestyle photos, or plates generated with
  `../gen/gen_image.py` (Gemini, with `--ref` for product/brand consistency).
- **Type** = ALWAYS this kit. Never let a model render headline/CTA/offer text into the
  image itself. Text lives in these HTML templates so it is crisp, on-brand, and editable
  without a re-generation.

## Install (once)

```bash
cd runtime/static-kit
npm install
npx playwright install chromium
```

## Run it

```bash
node render.js <batch.json>
python3 tools/sheet.py <finals-dir> sheet.jpg [cols]
```

`render.js` launches one headless Chromium instance and renders each variant in the batch
to a PNG. `tools/sheet.py` tiles a directory of rendered PNGs into one labeled contact
sheet for review.

## batch.json schema

```json
{
  "out_dir": "/abs/path/to/finals",
  "templates_dir": "/abs/path/to/static-kit/templates",
  "variants": [
    {
      "id": "f1-benefits",
      "template": "benefit-bubbles",
      "w": 1080,
      "h": 1350,
      "fields": {
        "logo": "/abs/path/logo.png",
        "headline": "Crunch Without the Junk",
        "sub": "Baked with olive oil and a pinch of sea salt.",
        "img": "/abs/path/product.png",
        "bullets": ["Five ingredients", "Baked, never fried", "No seed oils"],
        "offer": "20% off your first box",
        "cta": "Shop Now"
      }
    },
    {
      "id": "vs-table-1",
      "template": "vs-table",
      "fields": {
        "logo": "/abs/path/logo.png",
        "headline": "Not All Crackers Are Equal",
        "col_attr": "",
        "col_left": "The usual box",
        "col_right": "Ours",
        "img": "/abs/path/box.png",
        "offer": "Try the difference",
        "cta": "Shop Now",
        "rows": [
          "<div class=\"row\"><div class=\"cell attr\">Oil</div><div class=\"cell left\">seed-oil blend</div><div class=\"cell right\"><span class=\"yes\">✓</span>olive oil</div></div>"
        ]
      }
    }
  ]
}
```

- `out_dir`: absolute path, created if missing. Each variant writes `<id>.png` here.
- `templates_dir`: defaults to `./templates` next to `render.js`.
- `variants[].template`: filename (without `.html`) in `templates_dir`.
- `variants[].w` / `.h`: viewport size, default 1080x1350.
- `variants[].fields`: `{{key}}` substitutions. Strings are injected verbatim. Arrays are
  joined; each item is wrapped in `<div class="bullet">...</div>` unless it starts with
  `<` (pre-built HTML, e.g. `vs-table` rows).
- Any `{{placeholder}}` left unfilled becomes an empty string and is logged as a warning.
  Check the render log if a field looks missing.

Every claim string in a batch is legal surface: it must come from the client's
`approved-claims.md` or be flagged `[NEEDS APPROVAL]` (SKILL.md section 7).

## Templates

Open any template to read its field list and the design-law notes in its header comment.
They are layouts, not looks: palette and fonts come from `tokens.css`.

| family | templates |
|---|---|
| product-led | `photo-hero`, `hero-callouts`, `benefit-bubbles`, `product-rail`, `flatlay`, `orbit`, `device-photo` |
| scene-led | `scene-hero`, `seamless-hero`, `appetite`, `portrait-column`, `stickers-photo` |
| proof / evidence | `evidence-column` (verbatim quote column with a shared terminal word, field `invariant`), `evidence-wall`, `vs-table`, `split-screen`, `timeline-hero`, `week-hero` |
| voice / editorial | `editorial-card`, `letter`, `question-hook`, `ugc-caption`, `annotation-card`, `polaroid`, `comic` |
| offer | `offer-led`, `mega-promo` |
| character | `character-hero`, `character-brandmark`, `mascot` |

## Theming a client

`tokens.css` ships as a neutral starter theme. Per client, set the palette from the
brand's own site (intake writes harvested colour candidates to
`<work>/<client>/brand/palette-CANDIDATES.md` and font names plus any downloaded files to
`<work>/<client>/brand/fonts/INDEX.md`; you choose the final values) and put the brand's licensed web fonts in
`fonts/` under the names `tokens.css` documents. With no font files present everything
falls back to system fonts, so renders always work offline. Do not fork the templates
per client; only the token values change.

## Rules

- No em dashes in any template or copy.
- No external fetches, no webfonts from a CDN. Everything renders offline.
- `.canvas` uses `overflow:hidden` as a safety net, but templates are built to fit
  realistic copy (headlines of 5 words or fewer, subs up to 120 chars, 4-5 bullets of 34
  chars or fewer) without relying on clipping.
- Before shipping any batch, put the renders next to your North Stars and ask "does this
  hold up?" If not, it does not ship.
