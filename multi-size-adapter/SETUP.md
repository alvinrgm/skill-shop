# Setup: Multi-Size Creative Adapter

Takes one ad creative (or a folder of them) plus a list of target sizes, and returns
**natively re-composed, designer-ready starting points** per size — each output looks designed
for that format from scratch, with the copy kept word-for-word from the original.

**Important:** this produces starting points, not finished ads. Every size still needs a
design pass before it ships.

---

## Fastest start (one paste)

Drop this folder somewhere on your machine, open Claude Code in it, and paste:

> "Set up the multi-size-creative-adapter skill in this folder. Check what's missing, walk me
> through anything I need to do myself, save our team's Gemini key for me, and tell me when
> it's ready to use."

That one sentence is the whole setup. Claude runs the checks, tells you in plain English if
anything is missing, and asks you for the Gemini key when it needs it.

---

## What you need

**You will not have to use a terminal.** You talk to Claude in plain English and it runs
everything for you — the setup checks, the resizing, the quality checks. The one thing you
need to do yourself is get the Gemini key from your team lead. Claude will walk you through
saving it in a way that keeps it out of the chat transcript, since it is a live payment
credential on your company's account.

| Thing | Required? | What it's for | How to get it |
|---|---|---|---|
| **Claude Code** | Yes | The app you actually talk to. It reads this skill, runs everything, looks at each generated image to check it, and writes your review sheet. | [claude.com/claude-code](https://claude.com/claude-code) — install, sign in with your work account, then open this folder in it. Needs a Claude subscription; **Claude usage is billed separately from the Google image generation below.** |
| **Python 3** | Yes | Runs the engine under the hood (you never type Python) | Most Macs already have it. On Windows, install from [python.org/downloads](https://www.python.org/downloads/) and tick "Add Python to PATH". On a managed work laptop this may need your IT team — ask Claude to check first, it'll tell you if you already have it. |
| **Pillow** (image library) | Yes, for the quality check | Measures every output during the check (safe zones, empty legal band), and handles any extra format outside the four built-in ones. Generating the four built-in formats does not use it. | Nothing to do: Claude installs it for you during setup. If your laptop blocks the install, generation still works but the measured checks are reported as NOT MEASURED. |
| **Team Gemini API key** | Yes | Powers the re-composition (the AI that redesigns each format) | **Ask your team lead** — one shared key for the whole team. Claude will set it up with you; it will avoid putting the key into the chat itself, because chat transcripts are saved to disk and this key can be charged to your company. |

### For the team lead: creating the shared key (one time, ~15 minutes)

**Read this first: a billed key is mandatory, not optional.** Google's image-generation
models are **not available on the Gemini free tier at all** — a free key does not produce
lower-quality images, it produces an error. So this setup is two things, not one: create the
key, then attach a payment method to the project behind it. Budget about 15 minutes, and
expect to need whoever at your company can approve a company card.

**Part 1 — create the key (~3 min)**
1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in with a Google account
   the team controls. A shared/work account beats someone's personal account: whoever's
   account this is owns the billing and the key.
2. Click **Get API key** → **Create API key**. Google creates a Google Cloud project behind
   the scenes if you don't already have one — that's normal, you don't have to configure it.
3. Copy the key somewhere safe for now. It won't work for this tool until Part 2 is done.

**Part 2 — turn on billing (~10 min, this is the part people get stuck on)**
4. In AI Studio, open the **API keys** or **Plan information** page and click **Set up
   billing** on the project your key belongs to.
5. **Select or create a Google Cloud Billing account.** This is the "billing entity" — it is
   a separate object from the Google account and the project. If your company already has one
   (many do, via Google Workspace or an existing Cloud footprint), pick it and skip creating
   a new one; that keeps this on an invoice finance already recognizes.
6. Enter the billing contact info and a payment method (company card).
7. Choose **Prepay** or **Postpay**. Prepay requires a **minimum $10 up front** (max $5,000);
   Postpay bills you in arrears where available.
8. Wait for the tier to flip — usually under 10 minutes. Bank-transfer payment methods can
   take days to clear, so don't do this the morning you need the tool.
9. **Verify the key before you hand it to anyone.** In Claude Code, in this folder, say:
   *"run the self-test."* It makes one small test image for about $0.13 and tells you plainly
   whether the key, the billing and the engine all work. If billing has not gone through yet
   it says so in one line instead of producing a confusing error later, in the middle of
   someone's real job. (The underlying command, if you prefer to run it yourself, is
   `python3 scripts/selftest.py` -- or `--dry-run` to check the setup without spending
   anything.)
10. Share the key with your designers however you normally share credentials — each of them
    pastes it into their Claude chat once, and Claude saves it on their machine.

**Three things worth deciding up front,** because the key is a live payment credential:
- **Set a budget alert** on that Cloud Billing account. Google offers alerts, not hard caps,
  so this is the only spend warning you get.
- **Put it on a shared team account, not a personal one.** If the account owner leaves the
  company, the key and its billing leave with them.
- **Know how to revoke it.** In Google AI Studio, open **Get API key**, select the key, and
  delete it — it stops working immediately everywhere. Do this if it is ever pasted somewhere
  it should not be, or when someone leaves the team, then issue a new one and have everyone
  paste the new one to Claude once. Sharing it over a password manager rather than chat makes
  this much rarer.

**What this costs.** Google prices Gemini 3 Pro Image at **$0.134 per generated image** at the
resolution this tool uses. So 10 creatives across all four formats is 40 images, **about
$5.40**. Two things that estimate does not include, both of which are real:
- **Retries.** A size can be re-generated twice — once if Google refuses the first request,
  once if the quality check fails — and each retry is billed, so a rough batch's worst case is
  about 3x the expected figure. Claude shows both the expected and the worst-case number
  before it starts.
- **Claude's own usage**, which is billed separately by Anthropic under your Claude
  subscription. Reading and checking every generated image is the part that makes the output
  trustworthy, and it is not free.

Claude always shows the image count and the cost estimate before generating, and waits for
your go-ahead. Actual charges appear in your Google billing console, which is the authority —
treat the figures here as planning numbers, since Google changes pricing.

**One useful side effect of being on the paid tier:** Google's terms say free-tier content
may be used to improve their products, while **paid-tier content is not used for product
improvement** and is processed under the Cloud Data Processing Addendum. Since this tool
requires the paid tier anyway, your creatives are covered by the paid-tier policy.

**What gets sent where (plain-English disclosure):** each generated size makes one HTTPS call
to Google's Gemini API carrying the source creative image and the resize instruction. These
are your public-facing ad creatives; nothing else on the machine is sent, and nothing is
published anywhere. If your company has rules about sending assets to third-party AI APIs,
clear it with the right person before rolling this out — the paid-tier data policy above is
usually the fact they'll want.

## Verify
Ask Claude to "check the setup" anytime and it runs the health check for you. (If you ever
want to run it yourself: `bash doctor.sh` on Mac, or
`powershell -ExecutionPolicy Bypass -File doctor.ps1` on Windows.)

## The four formats
This tool ships four formats, all of which the AI produces natively at the right shape:

| Format | Shape | Where it goes |
|---|---|---|
| **Square** | 1:1 | Instagram/Facebook feed, LinkedIn |
| **Portrait** | 4:5 | Instagram/Facebook feed (the taller, higher-performing feed slot) |
| **Story / Reel** | 9:16 | Instagram, TikTok, Facebook Stories and Reels |
| **Landscape** | 16:9 | YouTube, display, link posts |

Ask for "the standard set" to get all four, or name the ones you want. Other shapes (small
web banners like 728x90, for instance) are possible but are cropped rather than generated
natively, cost the same per image, and usually need a designer to redo them — ask Claude and
it'll explain the tradeoff before doing it.

## Run it (each time)
1. Open **Claude Code** in this folder.
2. Point Claude at the ad — by name ("the newest Northridge ad"), by folder, or by dragging the
   file onto the Terminal window to paste its path. **Dragging an image into the chat itself
   is not enough**: Claude can see it but the tool needs the real file. On first run Claude
   asks where your ads live, so after that you can usually just name one.
3. Say which formats you want, or **"the standard set"**.

Claude looks at each creative, then **shows you exactly how many images it will generate and
what that will cost, and waits for you to say go.** After that it produces every format,
**opens and checks every single output** (copy word-for-word, brand fidelity, safe zones,
artifacts) before telling you it's done. You get an `outputs/<campaign>/` folder with one
subfolder per format plus a `review-sheet.md` per creative showing what passed and what's
flagged.

## What it will and won't do
- Produces each size as a native re-composition: full-canvas layout, background continued,
  elements repositioned for the format. Copy is preserved **verbatim** — this tool never
  rewrites your ad copy.
- Sizes outside the model's supported shapes (very short banners like 728x90) are generated
  wide and precision-cropped to exact pixels; the review sheet notes it.
- Does **not** produce finished, ship-ready ads. A designer finishes each size.
- **Files come out larger than the nominal size** (roughly 2K on the long edge) and at the
  correct shape. Scale down in your design tool as part of finishing; never scale up.
- **Every generated image is marked as AI-generated, in two ways.** There is a signed
  "content credential" (C2PA) in the file's metadata, which most ad platforms strip on upload,
  and a **SynthID watermark in the pixels themselves**, which survives cropping, resizing,
  re-compression and screenshotting. Neither carries any information about you or your
  company. If your compliance team asks whether AI use stays detectable in the shipped asset:
  yes, via SynthID, even after a designer finishes the file.
- **Legal fine print is deliberately left blank.** AI cannot render small legal text reliably
  — it comes out subtly garbled, and wrong legal copy on a financial ad is a compliance
  problem. So the tool never generates it: it leaves clean empty space where your legal block
  sits, and **a person pastes the correct legal text back in during finishing.** This is by
  design and the review sheet reminds you every time. Headlines, sublines, and CTAs are kept
  word-for-word and are checked against the source; any miss is flagged.
- Never uploads or publishes anywhere. Output lands in a local folder only.
- If a generation fails (key issue, network), that size falls back to a mechanical resize and
  is flagged for rework — a batch never dies on one size.

## Example
See `samples/` for a full worked example: a mock base creative, the plan Claude wrote, and the
resulting sizes with their review sheet.
