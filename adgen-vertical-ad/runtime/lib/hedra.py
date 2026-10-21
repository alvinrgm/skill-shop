"""Thin Hedra API client. One key, one orchestrator, full pipeline.

Hedra exposes:
- POST /assets + /assets/{id}/upload   → upload your own image/audio
- POST /generations type=image          → generate an image (Nano Banana, Flux, etc.)
- POST /generations type=video          → generate video (Character 3 lip sync, Veo 3, Kling, etc.)
- GET  /generations/{id}/status         → poll
- GET  /assets?type=image|audio|video   → list assets to find URL after generation
- GET  /voices                          → list TTS voices

Generations DON'T return a download_url directly — instead they return an asset_id.
You then list /assets?type=X to find the asset and pull its `asset.url`.
"""
from __future__ import annotations
import os, time, json, requests
from pathlib import Path
from typing import Optional

BASE = "https://api.hedra.com/web-app/public"

# Curated model IDs (pulled from /models)
MODELS = {
    # Image gen — Nano Banana T2I is the best for stylized characters with text/labels.
    "image_nano_banana": "ae01e1fd-5917-4e79-a65c-983b322bc5ce",
    "image_nano_banana_pro": "96d9d17d-a350-41d7-bb2e-006ff0a099c1",
    "image_flux_pro": "77bdb23a-5306-4793-a1b8-d458da213ef5",
    # Image edit (image-to-image) — for swapping expressions on the same character.
    "image_nano_banana_i2i": "c32ec32d-9f90-4557-b463-f412ef0e51f0",
    # Lip sync — Character 3 is the talking-head model.
    "video_character_3": "d1dd37a3-e39a-4854-a298-6510289f9cf2",
    # B-roll video — Kling 2.6 Pro I2V is current best for stylized motion.
    "video_kling_2_6_pro_i2v": "f00f87c8-ec48-4e9c-bbb6-1e496c929f89",
    "video_veo_3_i2v": "fb657777-6b02-478d-87a9-e02e8c53748c",
}


class HedraError(RuntimeError):
    pass


class Hedra:
    def __init__(self, api_key: Optional[str] = None):
        self.key = api_key or os.environ["HEDRA_API_KEY"]
        self.s = requests.Session()
        self.s.headers["x-api-key"] = self.key

    # ---------- low level ----------

    def _get(self, path: str, **kw):
        r = self.s.get(BASE + path, **kw)
        if not r.ok:
            raise HedraError(f"GET {path} → {r.status_code}: {r.text[:400]}")
        return r.json()

    def _post(self, path: str, **kw):
        r = self.s.post(BASE + path, **kw)
        if not r.ok:
            raise HedraError(f"POST {path} → {r.status_code}: {r.text[:400]}")
        return r.json()

    # ---------- voices ----------

    def list_voices(self) -> list[dict]:
        return self._get("/voices")

    def find_voice(self, query: str) -> dict:
        """Find a voice by case-insensitive name match."""
        for v in self.list_voices():
            if query.lower() in v["name"].lower():
                return v
        raise HedraError(f"no voice matching '{query}'")

    # ---------- assets ----------

    def upload_image(self, path: Path) -> str:
        """Upload a local image file. Returns asset_id."""
        meta = self._post("/assets", json={"name": path.name, "type": "image"})
        asset_id = meta["id"]
        with open(path, "rb") as f:
            r = self.s.post(f"{BASE}/assets/{asset_id}/upload", files={"file": f})
            r.raise_for_status()
        return asset_id

    def upload_audio(self, path: Path) -> str:
        meta = self._post("/assets", json={"name": path.name, "type": "audio"})
        asset_id = meta["id"]
        with open(path, "rb") as f:
            r = self.s.post(f"{BASE}/assets/{asset_id}/upload", files={"file": f})
            r.raise_for_status()
        return asset_id

    def get_asset_url(self, asset_id: str, asset_type: str = "image") -> Optional[str]:
        """Find the public URL for a generated asset by listing recent assets."""
        # Hedra doesn't expose a single-asset GET, so we list and filter.
        assets = self._get(f"/assets?type={asset_type}&limit=50")
        for a in assets:
            if a["id"] == asset_id:
                return a.get("asset", {}).get("url")
        return None

    # ---------- generations ----------

    def generate_image(
        self,
        prompt: str,
        model_id: str = MODELS["image_nano_banana"],
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Submit an image generation. Returns the queued generation dict (has id, asset_id)."""
        body = {
            "type": "image",
            "ai_model_id": model_id,
            "text_prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        return self._post("/generations", json=body)

    def generate_i2i(
        self,
        reference_image_id: str,
        prompt: str,
        model_id: str = MODELS["image_nano_banana_i2i"],
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Image-to-image generation (expression swap etc). Returns queued generation dict."""
        body = {
            "type": "image_to_image",
            "ai_model_id": model_id,
            "start_keyframe_id": reference_image_id,
            "text_prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        return self._post("/generations", json=body)

    def generate_tts(self, voice_id: str, text: str) -> dict:
        """Generate TTS audio. Returns the queued generation dict (has id, asset_id)."""
        body = {
            "type": "text_to_speech",
            "voice_id": voice_id,
            "text": text,
        }
        return self._post("/generations", json=body)

    def generate_lipsync_video(
        self,
        image_id: str,
        audio_id: str,
        text_prompt: str = "",
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
    ) -> dict:
        """Generate a Character-3 lip-sync video from an image asset + audio asset."""
        body = {
            "type": "video",
            "ai_model_id": MODELS["video_character_3"],
            "start_keyframe_id": image_id,
            "audio_id": audio_id,
            "generated_video_inputs": {
                "text_prompt": text_prompt or "character speaking expressively",
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
            },
        }
        return self._post("/generations", json=body)

    def poll(self, generation_id: str, every: int = 4, max_wait: int = 600) -> dict:
        """Poll until status is complete or error. Returns final status dict."""
        start = time.time()
        last_status = None
        while time.time() - start < max_wait:
            s = self._get(f"/generations/{generation_id}/status")
            status = s.get("status")
            if status != last_status:
                print(f"  [{generation_id[:8]}] status={status} progress={s.get('progress')}")
                last_status = status
            if status == "complete":
                return s
            if status in ("error", "failed"):
                raise HedraError(f"generation {generation_id} failed: {s}")
            time.sleep(every)
        raise HedraError(f"generation {generation_id} timed out after {max_wait}s")

    # ---------- end-to-end helpers ----------

    def make_image(self, prompt: str, out_path: Path, aspect_ratio: str = "9:16",
                   model_id: str = MODELS["image_nano_banana"]) -> dict:
        """Generate an image, poll, download to out_path. Returns {id, asset_id, url, path}."""
        gen = self.generate_image(prompt, model_id=model_id, aspect_ratio=aspect_ratio)
        gen_id = gen["id"]
        asset_id = gen["asset_id"]
        print(f"  → image gen queued: gen={gen_id[:8]} asset={asset_id[:8]}")
        self.poll(gen_id)
        # Find the URL from the assets list
        url = self.get_asset_url(asset_id, "image")
        if not url:
            raise HedraError(f"image generation {gen_id} complete but no URL found for asset {asset_id}")
        # Download
        out_path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return {"id": gen_id, "asset_id": asset_id, "url": url, "path": str(out_path)}

    def make_i2i(self, reference_image_id: str, prompt: str, out_path: Path,
                 aspect_ratio: str = "9:16") -> dict:
        """Image-to-image: modify a reference image. Returns {id, asset_id, url, path}."""
        gen = self.generate_i2i(reference_image_id, prompt, aspect_ratio=aspect_ratio)
        gen_id = gen["id"]
        asset_id = gen["asset_id"]
        print(f"  → i2i gen queued: gen={gen_id[:8]} asset={asset_id[:8]}")
        self.poll(gen_id)
        url = self.get_asset_url(asset_id, "image")
        if not url:
            raise HedraError(f"i2i {gen_id} complete but no URL for asset {asset_id}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return {"id": gen_id, "asset_id": asset_id, "url": url, "path": str(out_path)}

    def make_tts(self, voice_id: str, text: str, out_path: Path) -> dict:
        """Generate TTS audio, poll, download to out_path. Returns {id, asset_id, url, path}."""
        gen = self.generate_tts(voice_id, text)
        gen_id = gen["id"]
        asset_id = gen["asset_id"]
        print(f"  → tts gen queued: gen={gen_id[:8]} asset={asset_id[:8]}")
        self.poll(gen_id, every=3, max_wait=300)
        url = self.get_asset_url(asset_id, "audio")
        if not url:
            raise HedraError(f"tts {gen_id} complete but no URL for asset {asset_id}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return {"id": gen_id, "asset_id": asset_id, "url": url, "path": str(out_path)}

    def make_lipsync(self, image_asset_id: str, audio_asset_id: str,
                     out_path: Path, text_prompt: str = "",
                     aspect_ratio: str = "9:16", resolution: str = "720p") -> dict:
        """Generate a lip-sync video, poll, download to out_path."""
        gen = self.generate_lipsync_video(
            image_id=image_asset_id, audio_id=audio_asset_id,
            text_prompt=text_prompt, aspect_ratio=aspect_ratio, resolution=resolution,
        )
        gen_id = gen["id"]
        asset_id = gen["asset_id"]
        print(f"  → lipsync gen queued: gen={gen_id[:8]} asset={asset_id[:8]}")
        # Lip sync takes longer
        self.poll(gen_id, every=5, max_wait=900)
        url = self.get_asset_url(asset_id, "video")
        if not url:
            # Sometimes status response itself has the url
            s = self._get(f"/generations/{gen_id}/status")
            url = s.get("url") or s.get("download_url")
        if not url:
            raise HedraError(f"lipsync {gen_id} complete but no URL")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return {"id": gen_id, "asset_id": asset_id, "url": url, "path": str(out_path)}
