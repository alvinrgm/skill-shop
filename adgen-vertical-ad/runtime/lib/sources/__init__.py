"""Source plugins — each one turns a scene dict into a built scene clip.

A source plugin implements the `Source` interface (see base.py) and registers
itself in the REGISTRY below. The pipeline looks up the right source by
scene["source"] and dispatches.

Adding a new source (e.g. Sora, stock footage, still image):
  1. Drop a new module under lib/sources/
  2. Subclass Source and implement `build(scene, ctx)`
  3. Register here under its key
"""
from __future__ import annotations
from .base import Source, BuildContext, BuiltScene

from .raw import RawSource
from .hedra_character import HedraCharacterSource
from .hedra_broll import HedraBRollSource
from .end_card import EndCardSource

REGISTRY: dict[str, type[Source]] = {
    "raw": RawSource,
    "hedra_character": HedraCharacterSource,
    "hedra_broll": HedraBRollSource,
    "end_card": EndCardSource,
}


def get(kind: str) -> type[Source]:
    if kind not in REGISTRY:
        raise ValueError(f"unknown source '{kind}'. known: {list(REGISTRY)}")
    return REGISTRY[kind]
