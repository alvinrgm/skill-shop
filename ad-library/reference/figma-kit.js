// ad-library FIGMA KIT: the helper block pasted at the top of every template-build use_figma call.
// Plain Figma Plugin-API JavaScript. Load the figma-use skill before any use_figma call.
//
// FILL THE KIT OBJECT FROM <brand>/state.json (never guess an id):
//   KIT.vars    colour variable ids by short name (state.vars, "color/<name>")
//   KIT.styles  text style ids by role (state.styles)      KIT.fonts  [family, style] per role
//   KIT.shadow  effect style id (state.shadow_style_id)
//   KIT.pack / KIT.card / KIT.proof   component ids (pack cutout, offer card, proof-bar set)
//   KIT.disclaimer  the default disclaimer line (from the truth ledger's offer row)
//   PAGE        the Templates page node (figma.root.children.find(p => p.name === "Templates"))
//
// RULES THE KIT ENCODES (each one cost a failed call once):
//   - canvas(): the ad is a VERTICAL auto-layout component, SPACE_BETWEEN, padding 80/60 (4x5) or
//     260/330 (9x16), so the top block, the hero and the bottom (proof bar + disclaimer) can never
//     collide. Photos and shades are ABSOLUTE children.
//   - txt(): t.name = prop || "label" (a null name rolls back the whole call). Width fixed, then HEIGHT auto.
//     Never resize() after textAutoResize = "HEIGHT" (it locks the height at 10px): NONE, resize, HEIGHT.
//   - avail(): the hero gets whatever height is left; never hand-place y.
//   - check(): run on every variant before returning; any issue = fix it in the same call or report it.
//   - Component properties are added on each variant BEFORE combineAsVariants.
//   - Photo slots: author every photo component at its slot size (4x5 1088x1350, 9x16 1080x1935) with
//     the image rect on FILL, so an INSTANCE_SWAP fits. Give 9x16 its own "Photo 9x16" property.
//   - A HORIZONTAL row clips when its counter axis is fixed: resize, then counterAxisSizingMode = "AUTO".
//   - Optional decade rule (off by default; turn it on per brand with KIT.decadeRule = true and
//     copy-rules.json "decade_lowercase_s": true): a caps-only display font has no lowercase, so
//     "1950s" needs setRangeFontName on the "s" with KIT.fonts.decadeS, and check() flags "1950S".

const KIT = {
  vars: { paper: "VariableID:<id>", paperDeep: "VariableID:<id>", accent: "VariableID:<id>", alert: "VariableID:<id>", ink: "VariableID:<id>", warm: "VariableID:<id>", cool: "VariableID:<id>" },
  styles: { xl: "S:<Display/XL>,", L: "S:<Display/L>,", caps: "S:<Caps/Label>,", num: "S:<Display/Number>,", serifL: "S:<Headline/Serif L>,", bodyL: "S:<Body/L>,", bodyM: "S:<Body/M>,", disc: "S:<Body/Disclaimer>,", quoteM: "S:<Quote/M>," },
  // neutral defaults: replace with the closest Figma fonts to the brand's site (state.fonts)
  fonts: { xl: ["Playfair Display", "Bold"], L: ["Playfair Display", "Bold"], caps: ["Inter", "Bold"], num: ["Playfair Display", "Bold"], serifL: ["Playfair Display", "ExtraBold"], bodyL: ["Inter", "Regular"], bodyM: ["Inter", "Regular"], disc: ["Inter", "Regular"], quoteM: ["Playfair Display", "Italic"] },
  decadeRule: false,          // optional decade rule; when true also set fonts.decadeS: ["<font with a lowercase>", "<style>"]
  shadow: "S:<shadow>,",
  pack: "<state.components.pack>", card: "<state.components.offer_card>", proof: "<state.components.proof_bar_set>",
  packNative: [0, 0],         // REPLACE: your pack cutout's pixel size (read it from brand/packs/pack-<sku>.png), for aspect-correct instances
  cardNative: [0, 0],         // REPLACE: your offer-card component's native pixel size, for aspect-correct instances
  disclaimer: "Free shipping on your first order. Terms apply.",
};
if (!KIT.packNative[0] || !KIT.cardNative[0]) throw new Error("figma-kit: fill in KIT.packNative and KIT.cardNative (your asset pixel sizes) first");

const uniqFonts = [...new Map(Object.values(KIT.fonts).map(f => [f.join("/"), f])).values()];
await Promise.all(uniqFonts.map(([family, style]) => figma.loadFontAsync({ family, style })));
const V = {}; const vv = await Promise.all(Object.values(KIT.vars).map(id => figma.variables.getVariableByIdAsync(id))); Object.keys(KIT.vars).forEach((k, i) => V[k] = vv[i]);
const P = (k, op) => { const p = figma.variables.setBoundVariableForPaint({ type: "SOLID", color: { r: 0, g: 0, b: 0 } }, "color", V[k]); return op == null ? p : Object.assign({}, p, { opacity: op }); };
const [PACK, CARD, PROOF] = await Promise.all([KIT.pack, KIT.card, KIT.proof].map(id => figma.getNodeByIdAsync(id)));
const GAP = 36;

function canvas(ratio, fill) { const H = ratio === "4x5" ? 1350 : 1920; const c = figma.createComponent(); c.name = `Ratio=${ratio}`; c.layoutMode = "VERTICAL"; c.resize(1080, H); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED"; c.paddingLeft = 100; c.paddingRight = 100; c.paddingTop = ratio === "4x5" ? 80 : 260; c.paddingBottom = ratio === "4x5" ? 60 : 330; c.primaryAxisAlignItems = "SPACE_BETWEEN"; c.counterAxisAlignItems = "CENTER"; c.clipsContent = true; c.fills = fill ? [P(fill)] : []; return { c, H }; }
function vstack(parent, name, gap, w, align) { const f = figma.createAutoLayout("VERTICAL", { name, itemSpacing: gap }); parent.appendChild(f); f.fills = []; f.resize(w, 10); f.primaryAxisSizingMode = "AUTO"; f.counterAxisSizingMode = "FIXED"; f.counterAxisAlignItems = align || "CENTER"; return f; }
function hstack(parent, name, gap, w, align) { const f = figma.createAutoLayout("HORIZONTAL", { name, itemSpacing: gap }); parent.appendChild(f); f.fills = []; if (w) { f.resize(w, 10); f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "AUTO"; } f.counterAxisAlignItems = "CENTER"; f.primaryAxisAlignItems = align || "CENTER"; return f; }
async function txt(parent, comp, prop, chars, st, color, w, align, op) { const t = figma.createText(); t.name = prop || "label"; t.fontName = { family: KIT.fonts[st][0], style: KIT.fonts[st][1] }; t.characters = chars; parent.appendChild(t); await t.setTextStyleIdAsync(KIT.styles[st]); t.fills = [P(color, op)]; t.resize(w, 100); t.textAutoResize = "HEIGHT"; t.textAlignHorizontal = align || "CENTER"; if (comp && prop) { const k = comp.addComponentProperty(prop, "TEXT", chars); t.componentPropertyReferences = { characters: k }; } if (KIT.decadeRule) fixDecades(t); return t; }
function fixDecades(t) { const re = /\b(1[0-9]|20)[0-9]0s\b/g; let m; while ((m = re.exec(t.characters))) { const i = m.index + m[0].length - 1; t.setRangeFontName(i, i + 1, { family: KIT.fonts.decadeS[0], style: KIT.fonts.decadeS[1] }); } }
function packI(parent, h, comp) { const i = PACK.createInstance(); parent.appendChild(i); i.resize(Math.round(KIT.packNative[0] * h / KIT.packNative[1]), h); i.effectStyleId = KIT.shadow; i.name = "pack"; if (comp) { const k = comp.addComponentProperty("Pack", "INSTANCE_SWAP", PACK.id); i.componentPropertyReferences = { mainComponent: k }; } return i; }
function cardI(parent, h) { const i = CARD.createInstance(); parent.appendChild(i); i.resize(Math.round(KIT.cardNative[0] * h / KIT.cardNative[1]), h); i.effectStyleId = KIT.shadow; i.name = "offer-card"; return i; }
function proofI(parent, tone) { const v = PROOF.children.find(x => x.name === `Tone=${tone}`); const i = v.createInstance(); parent.appendChild(i); i.name = "proof-bar"; return i; }
async function bottom(c, tone, col, op) { const b = vstack(c, "bottom", 16, 880); proofI(b, tone); await txt(b, c, "Disclaimer", KIT.disclaimer, "disc", col, 880, "CENTER", op); return b; }
function avail(c, H, top, bot) { return H - c.paddingTop - c.paddingBottom - (top ? top.height : 0) - bot.height - 2 * GAP; }
function svg(parent, m, name, w, h) { const n = figma.createNodeFromSvg(m); n.name = name; parent.appendChild(n); if (w) n.resize(w, h); return n; }
function check(c, H, name) { const is = []; const kids = c.children.filter(k => k.layoutPositioning !== "ABSOLUTE"); let sum = c.paddingTop + c.paddingBottom; kids.forEach(k => sum += k.height); sum += (kids.length - 1) * 24; if (sum > H + 1) is.push(`${name} ${c.name}: content ${Math.round(sum)} > ${H}`); for (const t of c.findAllWithCriteria({ types: ["TEXT"] })) { if (t.width < 40 || t.height > 900) is.push(`${name} ${c.name}: text ${t.name} ${Math.round(t.width)}x${Math.round(t.height)}`); if (KIT.decadeRule && /\b\d{4}S\b/.test(t.characters)) is.push(`${name} ${c.name}: decade with capital S in ${t.name}`); } return is; }
async function makeSet(name, desc, build, x, y) { const a = await build("4x5"); const b = await build("9x16"); const set = figma.combineAsVariants([a.c, b.c], PAGE); set.name = name; set.description = desc; a.c.x = 40; a.c.y = 40; b.c.x = 1200; b.c.y = 40; set.resizeWithoutConstraints(2320, 2000); set.x = x; set.y = y; set.fills = [{ type: "SOLID", color: { r: 0.91, g: 0.89, b: 0.86 } }]; return { id: set.id, name, variants: [a.c.id, b.c.id], issues: [...a.issues, ...b.issues] }; }

// A build function returns {c, issues}. Example skeleton (offer card):
// const r = await makeSet("Template / 01 Offer card", "offer-led, product huge, labels row", async (ratio) => {
//   const { c, H } = canvas(ratio, "paper");
//   const top = vstack(c, "top", 16, 880); await txt(top, c, "Headline", "Headline here", "xl", "ink", 880);
//   const bot = await bottom(c, "Light", "ink", 0.8);
//   const hero = packI(c, Math.min(avail(c, H, top, bot), ratio === "4x5" ? 700 : 900), c);
//   c.insertChild(1, hero);
//   return { c, issues: check(c, H, "01") };
// }, 0, 0);
// return r;
