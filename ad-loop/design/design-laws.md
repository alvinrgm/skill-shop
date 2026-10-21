# Static Ad Design Laws

Codified from a study of elite DTC statics running live in the Meta Ad Library, plus the
kill verdicts of real operator review rounds. Build your own reference corpus with
`runtime/static-kit/tools/harvest_inspo.py` (lands in `<work>/inspo/`) and add any NEW law
you learn to the end of this file: the corpus teaches, this file accumulates.

These laws are the SHIPPING GATE. A render that breaks one without a stated reason does
not go to the client.

## A. Composition laws

1. **One world per ad.** One colour field, ONE photograph, or ONE illustration world.
   Never stitch surfaces together. A canvas plus a footer bar plus a pill stack is the
   number-one template tell.
2. **Product at 40-70% of the canvas.** Huge, centred or gently tilted (2-4 degrees),
   with a soft, real contact shadow. A timid product reads as DIY.
3. **At most three text moments.** A hook, one support line and one micro proof (a badge
   or footnote). Everything else is cut or becomes another ad.
4. **Outer margins of about 9-10%** (roughly 100px on a 1080 canvas), with everything
   snapped to them. Headline scale is 10-14% of the canvas height.
5. **Zone dividers are shaped:** a wave, a torn edge, a card boundary, a photo edge. Never
   a straight full-width colour bar. That is a footer, not a design.
6. **No CTA slab bars.** The CTA is one small soft pill, a button inside the scene, or
   nothing at all, because the feed's own chrome supplies one. The URL is one quiet line.

## B. Image laws

7. **Photography or crafted 3D carries the ad.** That means an art-directed scene, a macro
   appetite shot, a drop-shoot flat-lay or a premium 3D render. A flat cutout on a flat
   field is acceptable ONLY in the monochrome-hero archetype, and only when the cutout is
   huge and has a real shadow.
8. **Label fidelity is sacred.** The pack is always the REAL pack shot, or a generated
   scene with the real cutout composited over the generated pack. Model-rendered labels
   never ship unless they pass the letter-perfect filter at delivery scale.
9. **Scatter the physical product.** Pieces around the pack, crumbs, ingredients, the
   product in use. Physical product makes a flat-lay tactile.
10. **Photo-plus-illustration hybrids are premium, not cheap.** Doodles over photos,
    illustrated worlds behind photoreal product, stick-figure comics. The artifice must be
    CRAFTED and consistent.
11. **A variant gets its own world.** The flavour or SKU extends into the background
    palette and props (a grape can gets a grape world).
12. **Lineups get a floor:** a reflection or a grounding surface, with an in-use vessel
    in front (a bowl, a glass, a plate) as the appetite anchor.

## C. Type laws

13. **One display family plus one workhorse family.** A display serif or slab for the
    hook, a clean sans or serif for support. Letterspaced all-caps ONLY for tiny labels,
    never headlines. Case carries tone: sentence case reads clinical or empathetic, Title
    Case reads as a brand statement, an ALL-CAPS condensed stack belongs to the promo lane
    only.
14. **Colour comes from the product's own world:** near-monochrome, with one accent used
    once. Type colour is sampled from the scene or pack, not added as decoration.

## D. Device laws

15. **Every ad carries ONE designed concept device** that dramatises the claim: a
    timeline or calendar strip, a row of benefit badges with one key number each, a seal
    with annotation arrows, a fake article card, phone caption pills, a two-panel comic.
    Layout alone is not a concept.
16. **Numbers made tangible.** Comparative concreteness beats adjectives: "as much
    protein as a bowl of chilli", "12g protein / 5g fibre / 2g sugar" (invented examples).
    Find the equivalent object, date or count.
17. **Badges are designed objects:** a rotated stamp, a scalloped sticker, a tilted
    guarantee tag. One per ad at most.
18. **Compliance microtype** (a regulator-style footnote) whenever a health-adjacent claim
    appears. It reads as polish AND covers you legally.

## E. Copy laws

19. **Hook patterns that recur in elite statics:**
    - *Cultural reference or enemy:* the product as the sidekick of something everyone is
      talking about.
    - *Visceral confession:* the plain-words outcome people actually want.
    - *Time or calendar anchor:* "by Friday, the 4pm slump is gone".
    - *Dialogue or skit:* two-panel exchanges.
    - *Question flip:* "still doing it the hard way?"
    - *Restock or scarcity* (promo lane only, and only if the brand allows it).
    Choose courage over safety. The support line does the compliance work.
20. **Wit is allowed in the support line** (emoji, arrows, asides) when the brand voice
    permits it. Per-brand voice rules in the client bible override this law.

## F. The judge gate (mandatory before delivery)

Open the renders NEXT TO three or more corpus images of the same archetype. Ask, per ad:
- Would this stop a thumb in the same feed as the corpus ad?
- One world? Product huge? Three text moments or fewer? Device present? No bars?
- Is the imagery CRAFTED (photo, 3D, scene) or a lazy cutout paste?
- Is any claim missing from the client's approved list?
- Is every element part of ONE designed system (law 21)?
- Do object proportions obey reality (law 24)?

Score each ad ship, fix or kill. An ad that merely follows the layout but lacks a device
or a crafted image is a fix, not a ship. A yes-looking ad that fails law 21 or law 24 is a
kill, not a fix.

Feed survival: run `runtime/feed-gate/` (`feedmock/render_infeed.py` judges the ad at true
phone scale inside feed chrome; `ablate.py` runs the chrome, phone and desaturation
ablations). Any FAIL is a fix item. Passing only grants "not killed by the medium",
never ship.

## G. One-designed-system laws

A batch can pass the section F gate and still not look like a human design team made
it. The bar is deliberate design, not photorealism.

21. **One designed system.** Type, plates, cutouts, pills and field are conceived together
    on one grid, with one palette and one light logic. They are never layered onto an
    image after the fact. Test: if an element could be deleted without re-composing the
    ad, it was decoration, so recompose.
22. **The image proves the headline.** Each can be fine alone. If they do not complete
    each other, the ad has no idea.
23. **Cutout grounding or death.** A cutout hero needs ALL of: a contact shadow, reflected
    colour, edge light matched to the field, and deliberate placement on the grid at a
    deliberate scale. A small paste in a corner is a kill. Integration is fixable;
    afterthought placement is not.
24. **Physical honesty of scale.** Generated scenes must obey real object proportions, the
    way a photographer's set would have them. A scene that lies about size reads as AI
    whatever the image quality. Check proportions explicitly at plate QA.
25. **Focal hierarchy.** One dominant element, one medium, one small. When everything is
    mid-size, nothing is designed. Push the product toward the top of the product-huge law
    (60-70%), crop tighter, shoot closer.
26. **Both halves equally considered.** In any comparison or split format, the "them" side
    gets the same design attention as ours. A placeholder grey field reads as a template.
27. **Copy register: plain declaratives.** Spoken, not written, in the brand's own voice,
    with zero cleverness for its own sake (a plain line like "we made it simpler. you'll
    notice." beats any pun; invented example). Voice problems live in headlines too, not just body copy.
28. **Concession is seasoning, never the lead.** An honesty play earns trust INSIDE a
    benefit-led ad. An ad that OPENS on what the product cannot do has no idea to sell.
    Lead with the benefit and use the concession as the credibility beat.
29. **Never enlarge a photo past its resolution.** An extreme macro crop of a normal pack
    shot shows compression noise, soft focus and warped label geometry, which reads as a
    BROKEN RENDER, not intimacy. Macro framing needs an image captured at macro. A device
    (an annotation, a circle) cannot rescue an under-resolved plate. Corollary: every final
    gets a fresh-eyes "does anything look broken, warped or artifacted?" pass at 1:1,
    separate from taste judging.
30. **No quote bars.** The vertical hairline beside a support or reply line (the "|"
    speech marker) is banned. It reads as template furniture. Mark a change of voice with
    indent, scale, weight or colour, never a drawn rule.
31. **No logo for the logo's sake.** Meta shows the page handle natively, so a standalone
    logo or wordmark is redundant chrome. The branding moment is THE PRODUCT IN FRAME. If
    the product with its visible logo is in frame, add no other mark. If no product is in
    frame, the handle still carries attribution: add identity only when the design truly
    calls for it, and flag that as a deliberate choice. Judge corollary: "brand illegible at
    glance or blur" is NOT a fail for Meta placements when the product is present.

## Format archetype menu (pick per angle; do not force them all)

| archetype | anatomy |
|---|---|
| monochrome hero | field + display hook + huge product + 2 naked callouts with arrows + 1 stamp |
| concept-device photo | full-bleed photo, device rendered INTO the scene, hook in the negative space |
| editorial card | brand field + article card + giant serif question + arrow + product breaking the card |
| appetite or lifestyle hero | pure photography, one text moment or none |
| environment + stickers | product in a real scene + 2-3 die-cut benefit stickers + stat trio |
| mega-type promo | stacked condensed caps fill the frame + small product + tilted guarantee badge |
| comic or skit | hand-drawn panels + dialogue headlines + product intro + icon stats + microtype |
| flat-lay drop | overhead product + scattered pieces + doodle layer + textured display type |
| UGC caption | phone photo + caption pills (organic lane) |

Map each archetype to 2-3 images in your own `<work>/inspo/` corpus and note them here,
so the section F gate always has same-archetype references.
