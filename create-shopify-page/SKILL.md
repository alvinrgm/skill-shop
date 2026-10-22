---
name: create-shopify-page
description: >-
  Build a Shopify landing page end to end: verified facts, two audience versions designed
  in Figma, a 4-agent review, v2 plus mobile, theme code pushed to an unpublished test
  theme, and launch only on the user's typed yes. Use for "/create-shopify-page",
  "create a shopify page", "build a landing page for <brand>", "make an LP for <product>".
  Not for product page (PDP) template redesigns or ads.
---

# Create Shopify Page

A light loop that ships real landing pages: one strong model writes the copy and designs
the page in Figma, four read-only reviewers react, the user steers with Figma comments,
and the approved design is compiled into theme code on a test theme. Nothing touches the
live store until the user types yes.

Not this skill: product page (PDP) template redesigns, metafields, catalog-wide templates,
and static or video ads.

## FIRST RUN: onboarding gate
If `.onboarded` does NOT exist in this folder, do this before any page work. Every
dependency is in `dependencies.yml`; walk them one at a time.
1. Run `bash doctor.sh` (Windows: `powershell -ExecutionPolicy Bypass -File doctor.ps1`)
   and read the ❌ lines.
2. **Node.js 22+** (`node`): needed by Shopify CLI. Link <https://nodejs.org/>; offer
   `brew install node` on a Mac.
3. **Shopify CLI** (`shopify_cli`): offer `npm install -g @shopify/cli@latest`. Docs:
   <https://shopify.dev/docs/api/shopify-cli>.
4. **Store access** (`store_access`): they need staff or collaborator access to the store
   with the Themes permission. Have them run
   `shopify theme list --store <store>.myshopify.com` and sign in when the browser opens.
   It must list the themes, with one marked live.
5. **Figma MCP server** (`figma_mcp`), the one doctor can't verify: easiest is
   `claude plugin install figma@claude-plugins-official` (it also brings Figma's
   `figma-use` and `figma-design-to-code` skills); manual route
   `claude mcp add --transport http figma https://mcp.figma.com/mcp`. Then restart, run
   `/mcp`, pick figma, authenticate. Guide:
   <https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/>.
   Verify by checking that `use_figma` and `get_design_context` are in your tool list.
   Building in Figma needs an edit seat on the file.
6. **Shopify store connector** (`shopify_mcp`, optional): lets you read products, prices
   and reviews without the CLI. Without it, read them from the live site and the admin.
7. Re-run `bash doctor.sh`. When the required deps are ✅ and the Figma tools are present,
   write `.onboarded` (`date > .onboarded`) and ask the intake questions below.

---

## Step 0. Intake (one message, all at once)
Ask only what you can't find:
1. Brand, store (`<store>.myshopify.com`), product(s), the offer (for example a bundle
   discount or free shipping over a threshold) and its exact terms.
2. Who the page is for. Default: two audiences, one version each (for example A =
   experienced runners who know the category, B = first-time buyers).
3. Where traffic comes from (which ad or angle the page must match).
4. Which Figma file to build in. Default: the brand's existing design file. Never a file
   someone else owns without their OK.

## Step 1. Facts
- Get prices, sizes, variants and review counts from the store (connector or admin) and
  the live site. Never guess a number.
- Get the angle and context from the user's notes, briefs and past ads.
- Make a **VERIFY list** of anything unconfirmed (discount code active, kit contents,
  offer mechanics). It goes on the Figma canvas and stays until resolved.

## Step 2. v1 in Figma
Load the `figma-use` skill first if it is installed.
- Build both versions on a new page `LP · mm/dd · <topic> (A/B)`: 1440 desktop frames
  side by side.
- Put a brief card above each version: who it's for, positioning, big idea, section order.
- Claude writes the copy. Every claim comes from step 1.
- Use only the brand's real photos (from the file's assets or the store). No generated
  product images. No made-up reviews: leave a labeled review slot until real ones are pulled.
- All text stays on editable text layers.
- Send the user the link.

## Step 3. Review (4 read-only agents, launched together)
Write a short context file (audiences, offer, facts, what each page must do). Then spawn,
in one message, using the briefs in `reference/reviewer-briefs.md`:
1. A design and UX reviewer.
2. A second senior reviewer, on a different strong model if one is available, for fresh eyes.
3. One buyer persona per audience, each reacting to its own page.
Reviewers get screenshots and the context file. They get no write tools.

## Step 4. v2 and mobile
- Build v2 frames NEXT TO v1. Never overwrite v1.
- Add stickers (`V1 · ORIGINAL · BEFORE REVIEW`, `V2 · LATEST · AFTER REVIEW`) and a
  one-line "v2 changes:" note per version.
- Pull real reviews from the store's reviews app (Judge.me, Okendo, Yotpo, Stamped...)
  into the slots, with each reviewer's name exactly as published.
- Build 390 mobile frames for v2.
- Ask the user to look and leave comments in Figma.

## Step 5. The user's review
Pull every Figma comment, act on it, reply to each one ("claude: done, ..."), and resolve
only once the change is in. Repeat until the user says "build it".

## Step 6. Shopify build (test theme only)
Load `figma-design-to-code` if it is installed. Use the Figma copy word for word and real
images only. The full safety checklist is `reference/shopify-safety-checklist.md`; the
essentials:
- Namespaced files: `sections/<prefix>-*.liquid`, `templates/page.<suffix>.json`, CSS
  scoped to one root class, images uploaded as theme assets.
- Name sections clearly in the theme editor ("Socks LP: hero + photo").
- Find the real live theme id first with `shopify theme list` (role `live`); a saved
  environment in `shopify.theme.toml` can be stale.
- Push only to an UNPUBLISHED theme, ideally a fresh duplicate of the live theme. Never
  push to live, and never publish an old sandbox theme (it drops newer live-only changes).
- Create the Shopify pages HIDDEN, with the template suffix and an SEO title and description.
  Theme commands can't create pages: do it in the admin (Online Store > Pages > Add page,
  Visibility: Hidden, Theme template: `page.<suffix>`, then the SEO fields), or with a
  Shopify connector that can create pages.
- Preview: hidden pages return 404, so preview through a visible page:
  `/pages/<any-visible-page>?view=<suffix>&preview_theme_id=<id>`.
- Check at 1440 and 390: no overflow, add to cart works, the offer flow works, any email
  popup is hidden on these templates only, and the text matches Figma.
- Diff against live: list every file as new or modified. A modified shared file (for
  example `layout/theme.liquid`) gets its own patch built on live's current copy.
- Send the user a review table: change | preview link | what to check.

## Step 7. Launch (the user's typed yes, every time)
- The user (or the store's theme owner) pushes the listed files only:
  `shopify theme push --theme <live-id> --only <file> ... --nodelete`. Then pull live
  again and confirm nothing else changed.
- Unhide the pages only on their OK.
- Check that discount codes are active and whether they stack with automatic discounts.
- Check that tracking fires once on the CTA. Place one test order only if they approve.

## Known gotchas
- A Shopify connector may be signed in to a different store. Check the shop name first.
- `shopify theme pull --path` may not find the toml environment. Pull into a separate
  mirror folder instead.
- Never claim done from theme files. Claim it from the rendered preview URL.

## Done means
Both pages exist hidden on Shopify, both pass on the test theme, and the user has the
preview links and the launch steps. Live only after step 7.

---
Free from Rise Growth Marketing (risegm.com/skills). CC BY 4.0, see `LICENSE.txt`.
Feedback or bugs: open an issue at github.com/alvinrgm/skill-shop.
