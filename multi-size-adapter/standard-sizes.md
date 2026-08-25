# Formats

This tool ships **four formats**. They were chosen because the AI generates each one natively
at the correct shape — nothing is cropped, nothing is stretched, and no extra software is
needed to produce them.

| Ask for it as | Shape | Typical pixel size | Where it runs |
|---|---|---|---|
| **Square** | 1:1 | 1080x1080 | Instagram/Facebook feed, LinkedIn |
| **Portrait** | 4:5 | 1080x1350 | Instagram/Facebook feed (taller slot, usually the strongest feed performer) |
| **Story / Reel** | 9:16 | 1080x1920 | Instagram, TikTok, Facebook Stories and Reels |
| **Landscape** | 16:9 | 1920x1080 | YouTube, display placements, link posts |

Say **"the standard set"** for all four, or name the ones you want ("just square and story").

Files come out at roughly 2K on the long edge, which is larger than the pixel sizes above.
That is deliberate: you get more resolution to work with, and scaling down in your design tool
is lossless. Never scale up.

## Story/Reel safe zones
For 9:16, text, logo and buttons sit between **15% and 75%** of the height. Above 15% is where
the platform puts its own interface (username, caption, buttons) on top of your ad; below 75%
is the area kept clear so you can paste your legal text back in. Every 9:16 output is measured
against those two lines before it reaches you.

## Asking for other formats
Other shapes are possible but come with real tradeoffs, so they are opt-in rather than
default. A small web banner (728x90, 300x250, 160x600) has to be generated at a wider shape
and then cropped down, which means:

- **You pay the same per image** as a full-size format, for a fraction of the usable pixels.
- **They are the most likely to need rework** — extreme shapes leave the AI very little room,
  so a designer often ends up repositioning things by hand anyway.
- **They need one extra piece of software** (the Pillow image library), which Claude will
  install for you if you decide to go ahead.

Ask for one and Claude will explain the tradeoff before doing it. Often the faster path is to
let it build the square version well, then have a designer lay out the banner properly in
Figma from that.

## Copy limits, for reference
This tool keeps your copy **word-for-word** and never rewrites it. These limits are here so
you can judge whether a given format can carry the full copy — if it can't, that's a call for
a person to make, not something the tool will quietly do for you.

| Channel / field | Typical limit |
|---|---|
| Meta feed headline | ~40 characters |
| Meta feed primary text | ~125 characters before "See more" |
| Google responsive display, short headline | 30 characters (hard limit) |
| Google responsive display, long headline | 90 characters (hard limit) |
| LinkedIn single image ad headline | ~70 characters |

Approximate, and platforms change them. Confirm against the current platform spec before
launch.
