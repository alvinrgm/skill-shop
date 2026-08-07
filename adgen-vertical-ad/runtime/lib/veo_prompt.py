"""Structured Veo 3.1 prompt builder.

Codifies Google DeepMind's 7-part prompt schema (Subject, Action, Context,
Camera, Movement, Style, Audio) into a typed dataclass. Compose the fields,
call `.render()`, get a prompt that hits Veo's tokenizer in the shape it
was trained on — instead of shoving everything into one wall of prose.

Why this exists:
- Unstructured prompts → inconsistent output across scenes.
- Wall-of-text prompts → Veo drops details near the end.
- Quote-only dialogue ("she says \"...\"") → subtitle hallucination.
- Re-describing a subject we already passed as an image → "zombie drift"
  where Veo flips features mid-shot.

Design rules baked in (sourced from DeepMind's Veo Prompting Guide +
Replicate/Runway engineering notes):
  - Colon dialogue syntax: `Character says: 'line'` (NOT quote-only).
  - Triple anti-subtitle lock: `(no subtitles)` inline + colon dialogue
    + negative_prompt at the SDK layer.
  - 150-300 chars optimal per prompt; past 400 chars recall drops.
  - When an image is passed as reference, DO NOT re-describe visible
    attributes (hair color, clothing, etc.) — only describe motion,
    voice, context. Re-describing causes feature drift.
  - Camera language uses film vocabulary: "medium close-up", "handheld
    shake", "slow dolly in", "rack focus" — NOT "zoom" or "pan around".

Usage:
    p = VeoPrompt(
        subject="32-year-old woman",
        action="speaks casually to her phone camera, mouth moving continuously",
        context="in her home kitchen, soft morning light",
        camera_angle="medium close-up, phone selfie framing",
        style="UGC TikTok confessional, phone-lens shallow DoF",
        dialogue="I used to be hungry ninety minutes after breakfast.",
        audio_sfx="ambient kitchen room tone, no music",
        voice_spec="warm 32yo American woman, slight vocal fry, mid-register",
    )
    prompt_str = p.render()
    negative = p.negative_prompt()
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# Default negative prompt.
#
# IMPORTANT: `negative_prompt` is NOT supported by Veo 3.1 (Lite or Standard)
# via Gemini API — it returns 400 INVALID_ARGUMENT. This constant is kept
# only for reference / future Veo versions. Anti-caption must come from:
#   (1) the inline "(no subtitles, no on-screen text)" appended to dialogue
#       lines in VeoPrompt.render()
#   (2) colon dialogue syntax ("She says: 'line'" vs bare quotes)
# Those two alone were sufficient to eliminate caption hallucination in
# our bakeoff. Do NOT pass `.negative_prompt()` to GenerateVideosConfig
# until Veo adds support.
DEFAULT_NEGATIVE = (
    "subtitles, captions, text overlay, on-screen writing, watermark, "
    "logo, lower thirds, UI elements, warped hands, extra fingers, "
    "morphing face, smooth plastic skin, over-stylized, cartoonish, "
    "motion blur artifacts, double mouth, teeth artifacts"
)


@dataclass
class VeoPrompt:
    """Structured prompt for Veo 3.1 (Lite, Fast, or Standard).

    Fill the fields you care about; `render()` composes them in the order
    Veo responds best to. Unused fields are skipped cleanly.

    Field groups:
      SUBJECT / ACTION / CONTEXT — the "what"
      CAMERA — angle + movement (two separate fields; Veo treats them
        differently)
      STYLE — film look, grade, lens character
      DIALOGUE — spoken line (rendered with colon syntax)
      AUDIO — everything non-speech: SFX, music, room tone
      VOICE_SPEC — held CONSTANT across scenes to keep character voice
        consistent (validated in scratch/voice_consistency_test.py)
      PERFORMANCE — emotional note for delivery ("weary", "thoughtful
        realization", "warm with a hint of a smile")
      NEGATIVE — passed separately to the SDK, not concatenated
    """

    # --- Required-ish (most scenes set these) ------------------------------
    subject: str = ""            # "32-year-old woman"  (OMIT if image ref)
    action: str = ""             # "speaks casually to her phone camera"
    context: str = ""            # "in her home kitchen, soft morning light"

    # --- Camera (two fields — Veo treats them separately) -----------------
    camera_angle: str = ""       # "medium close-up, phone selfie framing"
    camera_movement: str = ""    # "locked-off handheld, gentle sway"

    # --- Look ------------------------------------------------------------
    style: str = ""              # "UGC TikTok, iPhone 15 front camera, shallow DoF"

    # --- Speech + performance ---------------------------------------------
    dialogue: Optional[str] = None       # the actual spoken line
    performance: Optional[str] = None    # "relaxed, slightly weary confessional"
    voice_spec: Optional[str] = None     # HELD CONSTANT across scenes

    # --- Audio ------------------------------------------------------------
    audio_sfx: str = ""          # "ambient kitchen room tone, no music"

    # --- SDK-layer negative (not concatenated into main prompt) -----------
    negative: str = DEFAULT_NEGATIVE

    # --- Image-ref mode: when True, subject-description is skipped in
    #     render() because re-describing a visible reference causes
    #     feature drift ("zombie drift").
    image_ref_mode: bool = False

    def render(self) -> str:
        """Compose fields into the 7-part prompt order Veo was trained on.

        Order (from DeepMind guide):
          1. Subject (skipped if image_ref_mode)
          2. Action
          3. Context / setting
          4. Camera angle
          5. Camera movement
          6. Style / film look
          7. Performance note
          8. Dialogue (colon syntax + inline "no subtitles" lock)
          9. Voice spec (held constant across scenes)
          10. Audio / SFX
        """
        parts: list[str] = []

        if self.subject and not self.image_ref_mode:
            parts.append(self.subject.strip().rstrip("."))
        if self.action:
            parts.append(self.action.strip().rstrip("."))
        if self.context:
            parts.append(self.context.strip().rstrip("."))
        if self.camera_angle:
            parts.append(self.camera_angle.strip().rstrip("."))
        if self.camera_movement:
            parts.append(self.camera_movement.strip().rstrip("."))
        if self.style:
            parts.append(self.style.strip().rstrip("."))
        if self.performance:
            parts.append(self.performance.strip().rstrip("."))

        # Dialogue — colon syntax + inline anti-subtitle lock.
        # This is the single highest-leverage rule in the whole guide:
        # `Character says: 'line' (no subtitles)` beats `"line"` every time.
        if self.dialogue:
            line = self.dialogue.strip().strip('"').strip("'")
            parts.append(f"She says: '{line}' (no subtitles, no on-screen text)")

        if self.voice_spec:
            parts.append(f"Voice: {self.voice_spec.strip().rstrip('.')}")

        if self.audio_sfx:
            parts.append(f"Audio: {self.audio_sfx.strip().rstrip('.')}")

        return ". ".join(parts) + "."

    def negative_prompt(self) -> str:
        """Return the negative prompt to pass to GenerateVideosConfig."""
        return self.negative

    def char_count(self) -> int:
        return len(self.render())

    def warnings(self) -> list[str]:
        """Lint the prompt before sending — surfaces known failure modes.

        Length thresholds are calibrated to Veo 3.1 (Lite/Fast/Standard),
        which handles longer prompts than Veo 2. Our bakeoff-winning
        prompts are 500-900 chars. Past ~1100 chars recall starts to drop.
        """
        w: list[str] = []
        rendered = self.render()
        n = len(rendered)
        if n > 1100:
            w.append(
                f"prompt is {n} chars — Veo 3.1 recall drops past ~1100. "
                f"Trim the tail (usually style/audio fields are trimmable)."
            )
        if n < 120 and self.dialogue:
            w.append("prompt is very short — Veo may fill in with generic choices.")
        if self.dialogue and '"' in self.dialogue:
            w.append(
                "dialogue contains a quote character — the builder strips it, "
                "but consider storing it clean."
            )
        if self.image_ref_mode and self.subject:
            w.append(
                "image_ref_mode=True but subject is set — subject will be "
                "skipped to prevent feature drift. Clear `subject` to silence."
            )
        if self.dialogue and not self.voice_spec:
            w.append(
                "dialogue set but voice_spec is empty — voices will drift "
                "across scenes. Hold voice_spec CONSTANT across a sequence."
            )
        return w


# --- Preset voice specs for consistency across a campaign ------------------
# These are the blocks to hold constant across every scene in a sequence.
# Borrowed from scratch/voice_consistency_test.py where we empirically
# validated Veo 3.1 Lite can reproduce the same voice across 3 calls when
# the spec is byte-identical.

SARAH_DEFAULT = (
    "warm, 32-year-old American woman with a slight vocal fry, mid-register, "
    "casual and conversational, relaxed pacing, very slight Midwestern "
    "flatness, natural phone-microphone audio quality, same woman's voice "
    "consistently throughout"
)


# --- Convenience factories for common scene types -------------------------

def ugc_talking_head(
    dialogue: str,
    performance: str,
    voice_spec: str = SARAH_DEFAULT,
    context: str = "in her home kitchen, soft natural morning window light",
    image_ref_mode: bool = True,
) -> VeoPrompt:
    """Standard UGC selfie talking-head scene.

    Assumes you're passing a FLUX portrait as image reference, so
    image_ref_mode=True skips subject re-description (prevents drift).
    """
    return VeoPrompt(
        subject="" if image_ref_mode else "32-year-old woman",
        action=(
            "speaks to her phone camera in a casual, conversational tone, "
            "mouth moving continuously as she talks, natural micro-expressions, "
            "subtle head tilts, occasional blinks"
        ),
        context=context,
        camera_angle="medium close-up, chest-up framing, phone selfie angle",
        camera_movement="locked-off handheld with gentle natural sway",
        style=(
            "UGC TikTok confessional, iPhone 15 front camera, shallow phone-lens "
            "depth of field, natural color grading, photorealistic, real-person "
            "feel not a model"
        ),
        dialogue=dialogue,
        performance=performance,
        voice_spec=voice_spec,
        audio_sfx="clean ambient kitchen room tone, no music",
        image_ref_mode=image_ref_mode,
    )


def product_interaction(
    dialogue: str,
    performance: str,
    product_description: str,
    voice_spec: str = SARAH_DEFAULT,
    context: str = "at her kitchen counter, soft morning window light",
) -> VeoPrompt:
    """Scene where the character holds / uses / interacts with a product.

    IMPORTANT: To actually lock the product's visual identity (logo, bag
    shape, label text), you need multi-reference support — which requires
    the FULL veo-3.1-generate-preview model, NOT Lite. Lite can only
    approximate from the text description. See docs/veo_prompt_guide.md
    section "Multi-reference / product scenes" for the trade-off.
    """
    return VeoPrompt(
        subject="",  # image ref mode — character comes from portrait
        action=(
            f"picks up and holds {product_description} at chest height, "
            "shows it briefly to the camera, then lowers it while continuing "
            "to speak naturally, mouth moving continuously"
        ),
        context=context,
        camera_angle="medium shot, chest-up, product visible in frame",
        camera_movement=(
            "locked-off handheld, slight natural sway, brief rack focus onto "
            "product when she raises it"
        ),
        style=(
            "UGC TikTok, iPhone 15 front camera, shallow phone-lens depth of "
            "field, natural color grading, photorealistic"
        ),
        dialogue=dialogue,
        performance=performance,
        voice_spec=voice_spec,
        audio_sfx="clean ambient kitchen room tone, no music",
        image_ref_mode=True,
    )
