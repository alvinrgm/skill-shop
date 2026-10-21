"""Source plugin interface.

A Source takes a scene dict from the brief and produces a single clip at
run_dir/scenes/{scene_id}.mp4 with audio baked in (VO or silence). The
assembler downstream only sees a uniform list of BuiltScene records.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BuildContext:
    """Everything a source plugin needs that isn't in the scene dict itself."""
    run_dir: Path
    raw_dir: Path             # root of brief's raw footage (if any)
    format: object            # lib.style.FormatSpec (avoids circular import)
    resolution: str           # passed through to Hedra sources
    tts_voice: str            # ElevenLabs voice name
    # Lazy-initialized clients (created on first use by the pipeline)
    tts: Optional[object] = None
    hedra: Optional[object] = None

    @property
    def width(self) -> int:
        return self.format.width

    @property
    def height(self) -> int:
        return self.format.height

    @property
    def fps(self) -> int:
        return self.format.fps

    @property
    def aspect_ratio(self) -> str:
        return self.format.key


@dataclass
class BuiltScene:
    id: str
    path: Path
    duration: float
    caption: Optional[str] = None
    kind: str = "scene"       # "scene" | "endcard" | "broll"
    # Optional per-sub-clip captions for montage scenes. Each tuple is
    # (start_offset_within_scene, duration, text). When set, the assembler
    # burns these instead of the scene-level `caption`.
    sub_captions: Optional[list] = None


class Source:
    """Base class for source plugins.

    Subclasses must implement build(). Optional hook `plan()` runs before build
    for sources that want to prefetch or validate.
    """
    name: str = "base"

    @classmethod
    def build(cls, scene: dict, ctx: BuildContext) -> BuiltScene:
        raise NotImplementedError
