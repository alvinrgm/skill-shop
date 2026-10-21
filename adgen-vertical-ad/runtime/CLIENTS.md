# adgen — client index

Canonical map of brand name → folder slug → structure state. **Read this in Phase 0 of the
adgen-vertical-ad skill before inferring any path.** The most common path-navigation bug is
guessing the folder name from the full brand name (e.g. `acme-widget-co/` instead of `acme/`).
Don't guess — look here.

This ships as an EMPTY TEMPLATE. Add one row per brand as you onboard it.

| Brand (canonical name) | Folder slug | Shopify slug | Structure | Notes |
|---|---|---|---|---|
| _(none yet)_ | | | | Add your first brand here, e.g. `\| Acme Co \| acme/ \| acme \| ✅ two-level \| mascot locked at acme/brand/characters/<name>/ \|` |

## Brand-name normalization (do this at message 1)

When the operator names a known client, normalize to the canonical name above before writing any
file or brief. Absorb typos and domain references silently, e.g.:
- "Acme Coo" → **Acme Co** (typo)
- "acme.example" / "acme" → **Acme Co** → folder `acme/`

## Folder law (enforced by `scripts/init_concept.sh`)

```
$ADGEN_HOME/<client>/
├── brand/                 # GLOBAL, concept-agnostic (bible, logo, product photos, scraped PDP, mascots)
│   └── characters/<name>/ # locked brand mascots (promote here once a char recurs in 2+ concepts)
└── concepts/
    └── <YYYY-MM-DD>-<angle>-<protagonist>/   # ONE per ad concept (see naming below)
```

## Concept naming convention

`<YYYY-MM-DD>-<angle>-<protagonist>` — all kebab-case, no spaces.

- **`<YYYY-MM-DD>`** = the date the concept was first started (its origin date), so concepts sort
  chronologically and you can always tell when a thread began.
- **`<angle>`** = the creative archetype / hook (`origin-story`, `manifesto`, `office-safari`).
- **`<protagonist>`** = the character or POV carrying the spot (`suds`, `otto`, `mom`).

Examples: `2025-03-14-sink-showdown-suds`, `2025-02-27-office-safari-otto`.

`scripts/init_concept.sh <client> <YYYY-MM-DD>-<angle>-<protagonist>` validates the pattern and
creates the full concept skeleton. It refuses slugs with spaces, missing date, or fewer than two
descriptor tokens.

### Pre-convention concepts (DO NOT rename in place)

If any of your concept folders predate this convention, leave them as-is: renaming breaks FCP's
cached asset uids (path-based) and any manifest references. New concepts use the convention from
day one.
