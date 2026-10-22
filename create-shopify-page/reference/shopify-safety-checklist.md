# Shopify safety checklist (step 6 and 7)

Work through it in order. Each line is a check, not a suggestion.

## Before writing code
- [ ] Confirm which store the CLI and any connector are signed in to (shop name matches).
- [ ] `shopify theme list --store <store>.myshopify.com`: note the live theme id (role `live`).
- [ ] Duplicate the live theme in the admin (Online Store > Themes > ... > Duplicate), or
      reuse a test theme only if it was duplicated from live after the last live change.
- [ ] Pull that test theme into a separate folder: `shopify theme pull --theme <test-id> --path <folder>`.

## Writing code
- [ ] Every new file is namespaced: `sections/<prefix>-*.liquid`, `snippets/<prefix>-*.liquid`,
      `templates/page.<suffix>.json`, `assets/<prefix>-*.css`.
- [ ] CSS is scoped under one root class, so nothing leaks into the rest of the theme.
- [ ] No edits to shared files unless necessary. Each necessary edit is listed, and is
      built on live's current copy of that file.
- [ ] Images are real brand images uploaded as theme assets or from the Files library.
- [ ] Text matches the approved Figma frames word for word.
- [ ] Sections have clear names and editable settings for headlines, images and buttons.

## Pushing to the test theme
- [ ] `shopify theme push --theme <test-id> --path <folder>`: never the live id here.
- [ ] Pages created HIDDEN, with the template suffix, SEO title and SEO description.
      (Admin: Online Store > Pages > Add page, Visibility Hidden, Theme template `page.<suffix>`.)

## Checking the preview
- [ ] Preview URL: `/pages/<any-visible-page>?view=<suffix>&preview_theme_id=<test-id>`.
- [ ] Desktop 1440 and mobile 390: no horizontal scroll, no overflow, images load.
- [ ] Add to cart works for every product and variant on the page.
- [ ] The offer works end to end (it applies correctly in the cart and at checkout).
- [ ] Popups that would cover the offer are hidden on these templates only.
- [ ] Tracking: the CTA click and add to cart fire once each (check with the browser's
      network panel or the analytics debugger).

## The launch list (send to the user)
- [ ] Every file, marked new or modified, with a one-line reason for each modified one.
- [ ] Review table: change | preview link | what to check.
- [ ] The exact push command for live, listing only those files:
      `shopify theme push --theme <live-id> --only <file> --only <file> --nodelete`.

## After the user's yes
- [ ] Push only the listed files to live. Pull live again and diff: nothing else changed.
- [ ] Unhide the pages only when they say so.
- [ ] Discount codes active; stacking with automatic discounts checked.
- [ ] One test order only with their approval.
