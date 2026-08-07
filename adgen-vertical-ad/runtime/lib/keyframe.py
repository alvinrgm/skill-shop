"""Gemini 2.5 Flash Image storyboard keyframe generator.

Architectural role: lock identity, product, and aesthetic at the IMAGE stage
before Veo ever touches a frame. The hypothesis is that 95% of first-shot
failures come from Veo inventing faces, bag designs, and skin tones from
scratch. Keyframes hand Veo a finished reference so it only animates.

Pipeline:
  1. Keyframe.generate() → calls gemini-2.5-flash-image via google-genai SDK.
  2. Resulting JPG lives in the storyboard cache dir.
  3. Veo receives the keyframe as i2v seed (image=) or reference_images=.
     That rewiring happens in the NEXT phase — this module is storyboard-only.

Image API:
  - Provider: Google AI (Gemini Developer API, same key used for Veo).
  - Model: gemini-2.5-flash-image ("Nano Banana").
  - Auth: GEMINI_API_KEY env var (read by genai.Client() automatically).
  - Multi-reference: pass image Parts inside the contents list — native support
    for zero, one, or multiple reference images in a single call.
  - Output: JPEG at 9:16 aspect ratio (via prompt instruction).

Cost: ~$0.03/image on Gemini 2.5 Flash Image (verify at ai.google.dev/pricing).

Reference mode semantics (Nano Banana):
  Gemini doesn't have a numeric `image_prompt_strength` knob. Reference
  adherence is controlled by prompt language injected by reference_mode:

    "strict_identity"  — "match the exact person in image 1; preserve face,
                          hair, skin tone, clothing identically"
                        Use for talking-head scenes needing exact face lock.

    "composite"        — "use image 1 as the person reference and image 2 as
                          the product reference; combine them naturally"
                        Use for scenes needing BOTH character AND product.

    "style_hint"       — "use the image only as a skin-tone and color reference;
                          do not copy the face, pose, or composition"
                        Use for hand/overhead scenes needing skin-tone bias only.

UGC aesthetic:
  Nano Banana defaults to polished output. The UGC_STYLE_PREFIX pushes hard
  against that with anti-polish tokens.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv

# Load .env from adgen project root (two levels up from lib/).
_LIB_DIR = Path(__file__).parent
_ADGEN_DIR = _LIB_DIR.parent
load_dotenv(_ADGEN_DIR / ".env")


# ---------------------------------------------------------------------------
# Aesthetic lock — prepended to EVERY keyframe prompt.
#
# NOTE on provenance: the physics_tokens block is lifted from an earlier UGC pipeline's
# `lib/photographySpecs.ts` `iphone-ugc` mode — that selector is the reason
# an earlier UGC pipeline's AI images read as real phone photos rather than AI renders. The
# key tokens are: 800 ISO digital noise, HDR shadow clipping, 24mm f/1.8
# barrel distortion, 3° handheld tilt, natural ambient 3000-5500K.
#
# Without these, Gemini defaults to clean raytraced-looking output — which
# is the "plasticky AI sheen" we saw in v4. Explicit phone-physics tokens
# dramatically improve perceived realism.
# ---------------------------------------------------------------------------
UGC_STYLE_PREFIX = (
    "amateur iPhone 15 selfie, candid not posed, authentic UGC, "
    "<physics_tokens mode=\"iphone-ugc\">"
    "Lens: 24mm wide angle (f/1.8), slight barrel distortion, edge softness. "
    "Lighting: Natural ambient, unmanipulated mixed light (3000K-5500K). "
    "Sensor: ISO 800 digital noise visible across the frame, "
    "computational HDR shadow clipping at hard edges. "
    "Camera: handheld micro-shiver, 3 degree off-axis tilt for authenticity. "
    "Style: imperfect, captured-in-the-moment realism, real person not a model, "
    "visible skin pores, fine hair flyaways, not airbrushed, no glossy sheen, "
    "NOT a cinematic grade, NOT a food-photography aesthetic, "
    "NOT shallow-DoF food-blog, NOT studio lit."
    "</physics_tokens>"
)

# Appended to every prompt — the anti-letterbox lock. Even with
# image_config.aspect_ratio="9:16" passed at the API level, Gemini sometimes
# pads the output with black bars when it thinks the scene composition is
# wider/taller than 9:16. Explicit NO-BORDERS language helps.
#
# IMPORTANT: do NOT use the word "screenshot" here — Gemini 3 Pro Image
# interprets "phone screenshot" literally and draws the camera-app UI
# (status bar, shutter button, PHOTO/VIDEO/PORTRAIT tabs) as part of the
# image. "Photograph" is the safe token.
FULL_BLEED_LOCK = (
    "the photograph fills the entire 9:16 frame edge-to-edge with NO black bars, "
    "NO letterbox padding, NO pillarbox padding, NO white borders, "
    "content extends to every edge of the frame. "
    "This is a finished photograph, NOT a screenshot of a phone screen, "
    "NOT a screen recording, NOT a camera-app UI — do NOT include status bars, "
    "time, battery icons, carrier name, flash icons, shutter buttons, "
    "PHOTO/VIDEO/PORTRAIT/PANO tabs, or any iPhone interface chrome."
)

# ---------------------------------------------------------------------------
# Gemini model ID.
#
# Upgraded from gemini-2.5-flash-image (old Nano Banana) to
# gemini-3-pro-image-preview per an earlier UGC pipeline's production usage — noticeably more
# photoreal output for talking-head and hand scenes. Slightly more expensive
# but the realism gap is large.
# ---------------------------------------------------------------------------
GEMINI_IMAGE_MODEL = "gemini-3-pro-image-preview"


class SceneType(str, Enum):
    """Framing preset for each scene category.

    These map to specific camera/composition tokens that ground Gemini's
    output. Using presets instead of free-form framing keeps the contact sheet
    compositionally consistent across all scenes.
    """
    SELFIE_CHEST_UP = "selfie_chest_up"
    SELFIE_WITH_PRODUCT = "selfie_with_product"
    PRODUCT_ON_COUNTER_OVERHEAD = "product_on_counter_overhead"
    HANDS_WORKING_OVERHEAD = "hands_working_overhead"
    FOOD_OVERHEAD_3_4 = "food_overhead_3_4"


_FRAMING_PRESETS: dict[SceneType, str] = {
    SceneType.SELFIE_CHEST_UP: (
        "chest-up selfie angle, phone held at arm's length slightly above eye "
        "level, slight upward tilt of the lens, subject fills upper two-thirds "
        "of the 9:16 frame, blurred kitchen background"
    ),
    SceneType.SELFIE_WITH_PRODUCT: (
        "chest-up selfie framing, phone held at arm's length, she is looking "
        "DIRECTLY INTO the camera lens with both eyes making clear eye contact "
        "with the viewer, product held at chest height with both hands and "
        "facing the camera lens, full bag label clearly visible and readable, "
        "slight upward tilt, blurred kitchen background"
    ),
    SceneType.PRODUCT_ON_COUNTER_OVERHEAD: (
        "phone held above the counter looking straight down, casual overhead "
        "iPhone snapshot, bag centered on a wooden kitchen counter, full label "
        "visible, natural window light, NO shallow depth of field, deep focus "
        "phone-camera look, NOT a food-blog overhead, NOT styled"
    ),
    SceneType.HANDS_WORKING_OVERHEAD: (
        "phone held above the counter looking straight down, casual overhead "
        "iPhone snapshot, hands and work surface fill the frame, wooden counter, "
        "soft natural window light, no face visible, deep focus phone-camera, "
        "NOT shallow DoF, NOT a styled food shoot, NOT cinematic"
    ),
    SceneType.FOOD_OVERHEAD_3_4: (
        "iPhone 15 snapshot at roughly 45 degrees above the food, casual "
        "real-home phone photo taken by a real person, deep focus phone-camera "
        "look, everything sharp front-to-back, NOT shallow depth of field, "
        "NOT a food-blog aesthetic, NOT cinematic backlight, NOT bokeh, "
        "ordinary home kitchen in the background, not a set"
    ),
}

# How each reference_mode translates to prompt language.
# {n} is replaced with the image number (1-indexed) when there's exactly one
# reference. For composite mode with two refs, the two-image string is used.
_REF_MODE_INSTRUCTIONS: dict[str, str] = {
    "strict_identity": (
        "match the exact person in image 1 precisely; preserve her face, hair "
        "color and style, skin tone, and clothing identically to image 1; "
        "same face, same person"
    ),
    "composite": (
        "use image 1 as the person reference: match her face, hair, skin tone, "
        "and clothing exactly; use image 2 as the product reference: match the "
        "bag label design, colors, and text exactly; combine them naturally "
        "in the same scene"
    ),
    "composite_product_only": (
        "use image 1 as the product reference: match the bag label design, "
        "colors, and text exactly"
    ),
    "style_hint": (
        "use the image only as a skin-tone and color palette reference; "
        "do not copy the face, pose, hair, or composition from the image; "
        "only pull the skin tone and warm lighting from it"
    ),
}

ReferenceMode = Literal["strict_identity", "composite", "composite_product_only", "style_hint"]


@dataclass
class Keyframe:
    """A single storyboard frame spec.

    Fill the fields, call render() to inspect the prompt, call generate()
    to hit the Gemini API and write a JPEG to disk.

    Args:
        scene_id: Short identifier used as the output filename stem.
        subject_description: Who/what is in the frame.
        action_description: What is happening — gesture, pose, product
            interaction.
        scene_type: One of the SceneType presets.
        reference_images: Zero or more local image Paths. Passed as inline
            Parts in the generate_content call. Order matters for reference_mode
            — for "composite", index 0 = person, index 1 = product.
        reference_mode: Controls the reference instruction language injected
            into the prompt. Ignored if reference_images is empty.
        extra_tokens: Any additional detail appended at the end of the prompt.
    """
    scene_id: str
    subject_description: str
    action_description: str
    scene_type: SceneType
    reference_images: list[Path] = field(default_factory=list)
    reference_mode: ReferenceMode = "strict_identity"
    extra_tokens: Optional[str] = None

    def render(self) -> str:
        """Compose the full prompt string.

        Order: style prefix → framing preset → reference instructions (if any)
               → subject → action → extras.
        """
        parts = [
            UGC_STYLE_PREFIX,
            _FRAMING_PRESETS[self.scene_type],
        ]

        if self.reference_images:
            n = len(self.reference_images)
            mode_key = self.reference_mode
            # For composite mode with only one image, fall back to product_only.
            if mode_key == "composite" and n == 1:
                mode_key = "composite_product_only"
            parts.append(_REF_MODE_INSTRUCTIONS[mode_key])

        if self.subject_description:
            parts.append(self.subject_description.strip().rstrip(","))
        if self.action_description:
            parts.append(self.action_description.strip().rstrip(","))
        if self.extra_tokens:
            parts.append(self.extra_tokens.strip())

        # Aspect-ratio + anti-letterbox lock.
        # We now pass image_config.aspect_ratio="9:16" to the API natively
        # (see generate()), but redundant prompt language helps the model
        # compose for the frame rather than generate-then-pad.
        # Note: avoid "phone-native framing" — reads as "camera-app screen".
        parts.append("9:16 vertical portrait aspect ratio")
        parts.append(FULL_BLEED_LOCK)

        return ", ".join(parts)

    def generate(self, out_path: Path) -> Path:
        """Generate the keyframe image and save it to out_path.

        Calls gemini-2.5-flash-image via generate_content with
        response_modalities=["IMAGE"]. Reference images (if any) are embedded
        as inline Parts after the text prompt.

        Returns out_path on success. Raises RuntimeError if the API returns
        no image part.
        """
        from google import genai
        from google.genai import types

        prompt = self.render()
        log(f"  prompt ({len(prompt)} chars): {prompt[:120]}...")

        # Build the contents list: text prompt first, then image refs.
        contents: list = [types.Part.from_text(text=prompt)]

        for ref_path in self.reference_images:
            assert ref_path.exists(), f"reference_image not found: {ref_path}"
            log(f"  attaching reference: {ref_path.name}")
            img_bytes = ref_path.read_bytes()
            # Determine mime type from suffix; default to jpeg.
            suffix = ref_path.suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))

        client = genai.Client()
        log(f"  submitting to {GEMINI_IMAGE_MODEL} ...")

        # Critical: pass aspect_ratio natively via image_config. Without this,
        # Gemini generates at its default ratio then pads with black bars to
        # match any aspect hint in the prompt. Source: an earlier UGC pipeline's geminiService.ts
        # `imageConfig: { aspectRatio, imageSize: "1K" }` is the production
        # path that avoids letterboxing.
        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="9:16"),
            ),
        )

        # Extract the first image part from the response.
        img_data: Optional[bytes] = None
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.data:
                        img_data = part.inline_data.data
                        break

        if img_data is None:
            raise RuntimeError(
                f"Gemini returned no image for scene '{self.scene_id}'. "
                f"Response: {response}"
            )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(img_data)
        log(f"  saved {out_path} ({out_path.stat().st_size // 1024} KB)")
        return out_path


# ---------------------------------------------------------------------------
# Skin-tone preservation helper (kept for call-site compatibility)
# ---------------------------------------------------------------------------

def skin_tone_reference(character_portrait: Path) -> tuple[Path, ReferenceMode]:
    """Return (path, reference_mode) for a skin-tone-only reference.

    Use this on scenes that show hands but not Sarah's face. "style_hint" mode
    injects prompt language that pulls skin tone without imposing Sarah's face
    or composition on the overhead shot.

    Usage:
        ref, mode = skin_tone_reference(PORTRAIT)
        kf = Keyframe(
            ...,
            reference_images=[ref],
            reference_mode=mode,
        )
    """
    return character_portrait, "style_hint"


def log(msg: str) -> None:
    """Timestamped print for pipeline visibility."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
