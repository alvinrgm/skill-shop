#!/usr/bin/env node
'use strict';

// Static-ad renderer: fills {{placeholder}} tokens in an HTML template with
// batch.json field values, then screenshots the result with Playwright.
// Usage: node render.js <batch.json>

const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright');

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Arrays become joined divs: items starting with "<" are injected verbatim
// (pre-built HTML, e.g. vs-table rows), everything else is wrapped in a
// .bullet div.
function fieldToHtml(value) {
  if (Array.isArray(value)) {
    return value.map((item) => {
      const s = String(item);
      return s.trimStart().startsWith('<') ? s : `<div class="bullet">${s}</div>`;
    }).join('');
  }
  return String(value);
}

function fillTemplate(html, fields, variantId) {
  let out = html;
  for (const [key, value] of Object.entries(fields || {})) {
    const replacement = fieldToHtml(value);
    const re = new RegExp('\\{\\{' + escapeRegExp(key) + '\\}\\}', 'g');
    // Function form avoids $-pattern special handling (copy can contain "$").
    out = out.replace(re, () => replacement);
  }
  out = out.replace(/\{\{[^}]+\}\}/g, (match) => {
    console.warn(`  ! ${variantId}: unresolved placeholder ${match} -> ""`);
    return '';
  });
  return out;
}

const USAGE = `usage: node render.js <batch.json>

batch.json: { "out_dir": "<folder for the PNGs>", "templates_dir": "<optional>",
              "variants": [ { "id": "...", "template": "<name in templates/>",
                              "w": 1080, "h": 1350, "fields": { ... } } ] }
Each variant renders to <out_dir>/<id>.png. See README.md for examples.`;

function fail(msg) {
  console.error(`render.js: ${msg}`);
  process.exit(1);
}

async function main() {
  const batchPath = process.argv[2];
  if (batchPath === '-h' || batchPath === '--help') {
    console.log(USAGE);
    return;
  }
  if (!batchPath) {
    console.error(USAGE);
    process.exit(2);
  }

  const resolved = path.resolve(batchPath);
  if (!fs.existsSync(resolved)) fail(`batch file not found: ${resolved}`);
  let batch;
  try {
    batch = JSON.parse(fs.readFileSync(resolved, 'utf8'));
  } catch (e) {
    fail(`batch file is not valid JSON: ${resolved} (${e.message})`);
  }
  const outDir = batch.out_dir;
  if (typeof outDir !== 'string' || !outDir.trim()) {
    fail('batch.json needs an "out_dir" string (the folder the PNGs are written to)');
  }
  const templatesDir = batch.templates_dir || path.join(__dirname, 'templates');
  if (!fs.existsSync(templatesDir)) fail(`templates_dir not found: ${templatesDir}`);
  const variants = batch.variants || [];
  if (!Array.isArray(variants) || variants.length === 0) {
    fail('batch.json has no "variants" to render');
  }
  for (const v of variants) {
    if (!v || !v.id || !v.template) fail('every variant needs an "id" and a "template"');
    const t = path.join(templatesDir, `${v.template}.html`);
    if (!fs.existsSync(t)) fail(`variant ${v.id}: no template ${t}`);
  }

  try {
    fs.mkdirSync(outDir, { recursive: true });
  } catch (e) {
    fail(`cannot create out_dir ${outDir} (${e.code || e.message})`);
  }

  const browser = await chromium.launch({ headless: true });

  for (const variant of variants) {
    const templatePath = path.join(templatesDir, `${variant.template}.html`);
    const rawHtml = fs.readFileSync(templatePath, 'utf8');
    const filledHtml = fillTemplate(rawHtml, variant.fields, variant.id);

    // Written next to the template so its relative "../tokens.css" link resolves.
    const tempPath = path.join(templatesDir, `.tmp_${variant.id}.html`);
    fs.writeFileSync(tempPath, filledHtml, 'utf8');

    const page = await browser.newPage({
      viewport: { width: variant.w || 1080, height: variant.h || 1350 },
      deviceScaleFactor: 1,
    });

    try {
      await page.goto(pathToFileURL(tempPath).href);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(250);

      const outPath = path.join(outDir, `${variant.id}.png`);
      await page.screenshot({ path: outPath });
      console.log(`saved ${outPath}`);
    } finally {
      await page.close();
      fs.unlinkSync(tempPath);
    }
  }

  await browser.close();
}

main().catch((err) => {
  const first = String((err && err.message) || err).split('\n')[0];
  if (/Executable doesn't exist|browserType\.launch/.test(first)) {
    fail(`Chromium is not installed for this Playwright: cd runtime/static-kit && npx playwright install chromium`);
  }
  fail(first);
});
