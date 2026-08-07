"""state — per-scene checkpoint + hash-based cache.

Each scene in a run carries two hashes:
  - visual_hash: derived from the fields that affect the visual/audio output
                 (everything except caption text). If this changes, rebuild.
  - script_hash: just the VO script. If it changes, regen TTS and rebuild (the
                 built clip has VO baked into its audio track).

The state file lives at run_dir/state.json. Load/save on every step.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path


def load_state(run_dir: Path) -> dict:
    p = run_dir / "state.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def save_state(run_dir: Path, state: dict):
    with open(run_dir / "state.json", "w") as f:
        json.dump(state, f, indent=2, default=str)


def hash_obj(obj) -> str:
    return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def scene_visual_hash(scene: dict) -> str:
    """Everything that affects what the scene looks/sounds like except caption text."""
    key = {k: v for k, v in scene.items() if k != "caption"}
    return hash_obj(key)


def scene_script_hash(scene: dict) -> str:
    return hash_obj(scene.get("script", ""))
