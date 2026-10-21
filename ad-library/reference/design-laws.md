# Static ad design laws

The taste law every template and every batch is judged against. A render that breaks one
without a stated reason does not ship.

Build your own reference corpus: pick 4-6 brands in or near your category whose statics you
admire, open each in the Meta Ad Library (https://www.facebook.com/ads/library/), and save 10-12
of their longest-running static ads into `$AD_LIBRARY_HOME/<brand>/library/reference/` with
`asset_library.py add --type reference`. Judge every batch next to 3+ of them (section F).

## A. Composition

1. **One world per ad.** A single colour field, ONE photograph, or ONE illustration world. Never
   stitch surfaces (canvas + footer bar + pill stack is the number one template tell).
2. **Product 40-70% of the canvas.** Huge, centred or gently tilted (2-4 degrees), with a soft real
   contact shadow. A timid product reads DIY.
3. **At most three text moments.** Hook, one support line, one micro proof (badge or footnote).
   Everything else is cut or becomes another ad.
4. **About 9-10% outer margins** (about 100 px on a 1080 frame), everything snapped to them.
   Headline scale is 10-14% of canvas height.
5. **Zone dividers are shaped:** a wave, a torn edge, a card boundary, a photo edge. Never a
   straight full-width colour bar (that is a footer, not a design).
6. **No CTA slab bars.** The CTA is one small soft pill, an in-scene button, or absent (the feed's
   own chrome supplies it). A URL is one quiet line.

## B. Image

7. **Photography or crafted 3D carries the ad:** an art-directed scene, a macro appetite shot, an
   overhead flat-lay, or a premium 3D render. A flat cutout on a flat field is acceptable ONLY in
   the monochrome-hero archetype, and then the cutout is huge with a real shadow.
8. **Label fidelity is sacred.** The pack is always the REAL pack photograph, on its own layer. In
   a generated scene the real label is composited back (label_composite.py) and the plate passes
   the print gate at wrong=0. Model-rendered labels never ship.
9. **Scatter the physical product.** Pieces around the pack, crumbs, ingredients, a pour: product
   physicality makes a flat-lay tactile.
10. **Photo x illustration hybrids are premium, not cheap:** doodles over photos, an illustrated
    world behind a photoreal product, a stick-figure comic. The artifice must be crafted and
    consistent.
11. **A variant gets its own world.** A flavour or SKU extends into the background palette and
    props (berry flavour, berry world).
12. **Lineups get a floor:** a reflection or a real surface, and an in-use vessel in front (a bowl,
    a glass, a plate) as the appetite anchor.

## C. Type

13. **One display family + one workhorse family.** A display serif or slab for the hook; a clean
    sans or serif for support. Letter-spaced all-caps ONLY for tiny labels, never headlines. Case
    carries tone: sentence case = clinical or empathetic, Title Case = brand statement, ALL-CAPS
    condensed stack = promo lane only.
14. **Colour from the product's own world:** near-monochrome, one accent used once. Type colour is
    sampled from the scene or the pack, not chosen as decoration.

## D. Device

15. **Every ad carries ONE designed concept device** that dramatises the claim: a timeline or
    calendar strip, a row of benefit badges with one key number each, a seal with annotation
    arrows, a fake article card, phone caption pills, a two-panel comic. Layout alone is not a concept.
16. **Numbers made tangible.** Comparative concreteness beats adjectives: "as much protein as a
    bowl of chilli", "12g protein / 5g fibre / 2g sugar" (invented examples). Find the equivalent object, date or count.
17. **Badges are designed objects:** a rotated stamp, a scalloped sticker, a tilted guarantee tag.
    One per ad at most.
18. **Compliance microtype** (a footnote) whenever a health-adjacent claim appears. It reads as
    polish AND covers you legally.

## E. Copy

19. **Hook patterns that recur in top accounts:**
    - *Cultural reference or enemy:* the product as the sidekick of something everyone is talking about
    - *Visceral confession:* the plain-words outcome people actually want
    - *Time or calendar anchor:* "by Friday, the 4pm slump is gone"
    - *Dialogue or skit:* two-panel exchanges
    - *Question flip:* "still doing it the hard way?"
    - *Restock or scarcity* (promo lane only, and only if true)
    Pick courage over safety; the support line does the compliance work.
20. **Wit belongs in the support line** (an aside, an arrow) when the brand voice permits it.
    Brand rules override (some brands ban emoji or snark).
21. **Copy register: plain declaratives.** Spoken, not written; "we"; zero cleverness for its own
    sake. Voice problems live in headlines too, not just body copy.
22. **Concession is seasoning, never the lead.** An honesty beat earns trust INSIDE a benefit-led
    ad; an ad that OPENS on what the product cannot do has no idea to sell.

## F. The judge gate (before delivery)

Open every final at full size NEXT TO 3+ reference ads of the same archetype. Per ad:
- Would this stop a thumb in the same feed as the reference ad?
- One world? Product huge? At most three text moments? Device present? Bars absent?
- Is the imagery CRAFTED (photo, 3D, scene) or a lazy cutout paste?
- Is every claim in the truth ledger?
- Is every element part of ONE designed system (law 23)? Do proportions obey reality (law 26)?
Score each ad ship / fix / kill. An ad that merely follows the layout but lacks a device or a
crafted image is a fix, not a ship. Failing law 23 or 26 is a kill, not a fix.
Also judge it at true phone scale (shrink the export to about 400 px wide next to a screenshot of
your feed): passing that only means the medium did not kill it, never that it ships.

## G. One designed system

23. **One designed system.** Type, plates, cutouts, pills and field are conceived together on one
    grid, one palette, one light logic, never layered onto an image after the fact. Test: if an
    element could be deleted without re-composing the ad, it was decoration; recompose.
24. **The image proves the headline.** Each may be fine alone; if they do not complete each other,
    the ad has no idea.
25. **Cutout grounding or death.** A cutout hero needs ALL of: a contact shadow, reflected colour,
    edge light matched to the field, and deliberate placement at deliberate scale. A small
    cornered paste is a kill.
26. **Physical honesty of scale.** Generated scenes obey real proportions (food : counter : pack as
    a photographer's set would have them). A scene that lies about size reads AI whatever its
    image quality. Check proportions explicitly at plate QA.
27. **Focal hierarchy.** One dominant element, one medium, one small. Everything mid-size means
    nothing was designed.
28. **Both halves equally considered.** In a comparison or split format, the "them" side gets the
    same design attention as yours; a placeholder grey field reads template.
29. **Never enlarge a photo past its resolution.** An extreme crop of a normal pack shot shows
    compression noise, soft focus and warped label geometry that read as a BROKEN render. Every
    final gets a fresh-eyes "does anything look broken, warped or artifacted?" pass at 1:1,
    separate from taste judging.
30. **No quote bars.** A vertical hairline beside a line of copy reads as template furniture. Mark
    a voice change with indent, scale, weight or colour.
31. **No logo for the logo's sake.** Meta shows the page name on every ad. When the product with
    its logo is in frame, add no extra mark. With no product in frame, add identity only if the
    design calls for it, and say it was a deliberate choice.

## Format archetype menu (pick per angle; do not force all)

| archetype | anatomy |
|---|---|
| monochrome hero | field + display hook + huge product + 2 callouts + 1 badge |
| concept-device photo | full-bleed photo, the device rendered INTO the scene, hook in the negative space |
| editorial card | brand field + article card + giant serif question + arrow + product breaking the card |
| appetite / lifestyle hero | pure photography, one text moment or none |
| environment + stickers | product in a real scene + 2-3 benefit stickers + a short stat row |
| mega-type promo | stacked condensed caps filling the frame + product small + tilted guarantee badge |
| comic / skit | drawn panels + dialogue headlines + product intro + icon stats + microtype |
| overhead flat-lay | overhead product + scattered pieces + doodle layer + textured display type |
| phone-caption (organic lane) | phone-register photo + caption pills in the brand's own voice (never a made-up testimonial) |
