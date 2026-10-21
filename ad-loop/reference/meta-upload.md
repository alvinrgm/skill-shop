# Handing a finished static to Meta (optional, draft-only)

**Default behaviour: RECOMMEND-ONLY.** The loop never writes to an ad account on its own.
When a concept ships, it produces an **upload packet** and stops:

```
<work>/<client>/statics/loop-<concept>/ship/
├── <concept>-4x5.png          1080x1350, the feed placement
├── <concept>-9x16.png         1080x1920, stories/reels (if the concept has one)
├── creative.json              primary text, headline, CTA, link URL, UTM url_tags,
│                              and the asset_feed_spec below with <HASH> placeholders
└── README.md                  the claims status of every line, and what still needs
                               a human signature before anything goes live
```

The operator uploads it in Ads Manager themselves, or tells Claude "upload it as a draft".
Everything below applies only to that second case.

## The rules for any account write (non-negotiable)

1. **Explicit words, every time.** An account write needs the operator's own instruction
   in this session ("upload <concept> to <ad account> as a paused draft"). A ship verdict
   is not an upload instruction. A teammate's message is not one either.
2. **PAUSED / draft only.** Every ad this skill creates is created `PAUSED`. Turning
   anything on, changing a budget, a bid, targeting, or an automated rule is out of scope
   for this skill. The human activates it in Ads Manager after their own review
   (claims/compliance included).
3. **Claims gate first.** Any line still marked `[NEEDS APPROVAL]` (SKILL.md section 7)
   blocks the upload. No exceptions for "it's only a draft".
4. **Log every write** with the operator's exact words and the ids returned, in
   `<work>/<client>/statics/loop-state/iterations.jsonl` (`"type": "account_write"`).

The tool for this is a Meta Ads connector in Claude Code (any MCP server that exposes
ad creative + ad creation for an ad account you administer). The loop works without one;
it just stops at the packet.

## The one-ad rule

**Multiple ratios of the same concept = ONE placement-customized ad, not N ads.** Separate
per-ratio ads split delivery learning and clutter the ad set. Settle the ad-count and
format question BEFORE the first write: creatives are **immutable**, so a wrong shape
costs a create, delete, recreate cycle per mistake.

## Getting the pixels in

1. **Disk upload through the connector** (an "upload media / upload image" tool), where it
   is available: local file to account library hash, no hosting needed.
2. **Upload once in Ads Manager** (Assets / Media library), then read the image hash back
   with the connector's ad-images tool and build the ad from it. This always works and
   needs no extra access.
3. If your workflow needs a public URL, use storage you or the brand already own (the
   brand's store file CDN, your own bucket). `curl -I` it and confirm `200` +
   `content-type: image/png` before any write. Never put anything non-public on a third
   party host.

> If a connector says a tool is "gradually rolling out", that is the connector gating its
> own tools, not a Meta API limitation. Fall back to option 2.

## The silent-failure trap (this is the one that bites)

**`image_url` inline inside an ad-create call's creative spec can silently drop the
image.** The call succeeds, returns an ad id, status PAUSED, and the ad renders only the
Page profile logo. No error anywhere.

**Correct path:** build the creative FIRST (account id, page id, link URL, image hash or
URL, message, headline, CTA, name), then create the ad referencing
`{"creative_id": "<id>"}`.

## One ad, both aspects (asset_feed_spec)

Image placement customization goes through a raw creative spec:

```json
{
  "name": "<name>",
  "object_story_spec": {"page_id": "<PAGE_ID>"},
  "asset_feed_spec": {
    "images": [
      {"hash": "<4x5_HASH>",  "adlabels": [{"name": "img_4x5"}]},
      {"hash": "<9x16_HASH>", "adlabels": [{"name": "img_9x16"}]}
    ],
    "bodies":  [{"text": "<primary text>"}],
    "titles":  [{"text": "<headline>"}],
    "ad_formats": ["SINGLE_IMAGE"],
    "call_to_action_types": ["SHOP_NOW"],
    "link_urls": [{"website_url": "<landing url>"}],
    "asset_customization_rules": [
      {
        "customization_spec": {
          "publisher_platforms": ["facebook", "instagram", "messenger"],
          "facebook_positions": ["story", "facebook_reels"],
          "instagram_positions": ["story", "reels"],
          "messenger_positions": ["story"]
        },
        "image_label": {"name": "img_9x16"},
        "priority": 1
      },
      {
        "customization_spec": {
          "publisher_platforms": ["facebook", "instagram", "messenger", "audience_network"],
          "facebook_positions": ["feed", "video_feeds", "marketplace", "search", "right_hand_column", "profile_feed", "instream_video"],
          "instagram_positions": ["stream", "explore", "explore_home", "profile_feed", "ig_search"],
          "messenger_positions": ["messenger_home"],
          "audience_network_positions": ["classic"]
        },
        "image_label": {"name": "img_4x5"},
        "priority": 2
      }
    ]
  },
  "degrees_of_freedom_spec": {"creative_features_spec": {"standard_enhancements": {"enroll_status": "OPT_OUT"}}}
}
```

Gotchas:

- **Image hashes, not URLs**, inside `asset_feed_spec`.
- **Every rule must enumerate positions explicitly.** A catch-all rule with platforms but
  no position arrays validates at creation and fails at render ("0 target rule(s) for
  format MOBILE_FEED_STANDARD, but exactly 1 target rule is expected").
- `standard_enhancements OPT_OUT` unless the operator wants Meta editing the art. Any AI
  disclosure setting is the operator's call: surface it, never infer it.
- **Reusing an existing creative keeps its post** (likes, comments, shares) because the
  new ad keeps the same story id. It does not carry delivery learning, and it cannot
  change copy, media or link. Rebuild only when one of those must change.
- UTMs survive reuse when `url_tags` use macros (`{{campaign.name}}`, `{{adset.name}}`,
  `{{ad.name}}`, `{{ad.id}}`).

## The verification gate (before you say "uploaded")

**API success is not upload success.** After every creative-bearing write:

1. Pull the ad preview for each placement that matters (at minimum the mobile feed and
   Instagram story formats for a dual-aspect ad).
2. If the tool returns only iframe HTML, render the preview URL in a browser and
   screenshot it.
3. **Look at the image.** The failure mode is the ad rendering the Page logo instead of
   the creative: invisible in every API response, obvious in one glance. Only after seeing
   the real art in both placements do you report "uploaded (paused)".

## Housekeeping

- Ads stay PAUSED until the human chain signs off. PENDING_REVIEW while paused is normal.
- If you created a broken draft in this session, tell the operator and offer to delete
  it (with their go-ahead). Name any test creative self-describingly
  ("ZZZ TEST ... DELETE ME") so it cannot be mistaken for real work.
- Heavy read loops can hit the ad account's rate limit and block other tools sharing it
  for a while. Batch reads and cache them locally.
