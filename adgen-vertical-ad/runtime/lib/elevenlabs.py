"""ElevenLabs v3 TTS client.

Supports inline emotional tags like [excited], [whisper], [urgent], [disgusted], [sigh].
Uses the v3 model (eleven_v3) for best prosody and emotion handling.

Usage:
    el = ElevenLabs()
    result = el.tts("Aria", "[excited] This is amazing!", Path("out.mp3"))
"""
from __future__ import annotations
import os, requests
from pathlib import Path
from typing import Optional

BASE = "https://api.elevenlabs.io/v1"

# Good voices for ad creative (Creator tier+)
RECOMMENDED_VOICES = {
    "aria": "9BWtsMINqrJLrRacOk9x",      # Female, expressive, warm
    "roger": "CwhRBWXzGAHq8TQ4Fs17",      # Male, authoritative
    "sarah": "EXAVITQu4vr4xnSDxMaL",      # Female, soft, friendly
    "laura": "FGY2WhTYpPnrIDTdsKH5",      # Female, upbeat
    "charlie": "IKne3meq5aSn9XLyUdCD",    # Male, casual, Australian
    "george": "JBFqnCBsd6RMkjVDRZzb",     # Male, warm, British
    "callum": "N2lVS1w4EtoT3dr4eOWO",     # Male, intense, transatlantic
    "river": "SAz9YHcvj6GT2YYXdXww",      # Non-binary, calm
    "liam": "TX3LPaxmHKxFdv7VOQHJ",       # Male, young, articulate
    "charlotte": "XB0fDUnXU5powFXDhCwa",   # Female, seductive, Swedish
    "alice": "Xb7hH8MSUJpSbSDYk0k2",      # Female, confident, British
    "matilda": "XrExE9yKIg1WjnnlVkGX",    # Female, warm, friendly
    "will": "bIHbv24MWmeRgasZH58o",        # Male, friendly, young
    "jessica": "cgSgspJ2msm6clMCkdW9",    # Female, expressive, American
    "eric": "cjVigY5qzO86Huf0OWal",        # Male, friendly, middle-aged
    "chris": "iP95p4xoKVk53GoZ742B",       # Male, casual
    "brian": "nPczCjzI2devNBz1zQrb",       # Male, deep, narrator
    "daniel": "onwK4e9ZLuTAKqWW03F9",      # Male, authoritative, British
    "lily": "pFZP5JQG7iQjIQuC4Bku",        # Female, warm, British
    "bill": "pqHfZKP75CvOlQylNhV4",        # Male, trustworthy, American
}


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabs:
    def __init__(self, api_key: Optional[str] = None):
        self.key = api_key or os.environ["ELEVENLABS_API_KEY"]
        self.s = requests.Session()
        self.s.headers["xi-api-key"] = self.key

    def list_voices(self) -> list[dict]:
        """List available voices."""
        r = self.s.get(f"{BASE}/voices")
        if not r.ok:
            raise ElevenLabsError(f"list_voices → {r.status_code}: {r.text[:400]}")
        return r.json().get("voices", [])

    def find_voice_id(self, name: str) -> str:
        """Find a voice ID by name. Falls back to hardcoded lookup if API fails."""
        # Try hardcoded first (faster, no API call)
        key = name.lower().strip()
        if key in RECOMMENDED_VOICES:
            return RECOMMENDED_VOICES[key]
        # Fall back to API search
        for v in self.list_voices():
            if name.lower() in v["name"].lower():
                return v["voice_id"]
        raise ElevenLabsError(f"no voice matching '{name}'")

    def tts(
        self,
        voice_name: str,
        text: str,
        out_path: Path,
        model_id: str = "eleven_v3",
        stability: float = 0.4,      # Creative range (0.35-0.45) — see reference/elevenlabs-dialogue-emotion.md
        similarity_boost: float = 0.75,
        style: float = 0.12,         # 0.0-0.15 for v3 expressive ad VO; NOT 0.6
        seed: Optional[int] = None,
        previous_request_ids: Optional[list] = None,
    ) -> dict:
        """Single-voice TTS, v3, inline audio tags. APPLY reference/elevenlabs-dialogue-emotion.md.

        Every line MUST carry ≥1 audio tag. Lock seed + settings per character across shots; pass
        previous_request_ids (≤3) for continuity. For 2+ character shots use dialogue() instead.

        Returns {voice_id, voice_name, path, model, request_id}.
        """
        voice_id = self.find_voice_id(voice_name)
        print(f"  → ElevenLabs TTS: voice={voice_name} ({voice_id[:8]}...) model={model_id}")

        body = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True,
            },
        }
        if seed is not None:
            body["seed"] = seed
        if previous_request_ids:
            body["previous_request_ids"] = previous_request_ids[:3]

        r = self.s.post(
            f"{BASE}/text-to-speech/{voice_id}",
            json=body,
            headers={"Accept": "audio/mpeg"},
        )
        if not r.ok:
            raise ElevenLabsError(f"tts → {r.status_code}: {r.text[:400]}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(r.content)

        size_kb = len(r.content) / 1024
        req_id = r.headers.get("request-id", "")
        print(f"  → saved {out_path} ({size_kb:.0f} KB)  request_id={req_id}")

        return {
            "voice_id": voice_id,
            "voice_name": voice_name,
            "path": str(out_path),
            "model": model_id,
            "request_id": req_id,
        }

    def dialogue(
        self,
        turns: list,
        out_path: Path,
        model_id: str = "eleven_v3",
        stability: float = 0.4,
        similarity_boost: float = 0.75,
        style: float = 0.12,
        seed: Optional[int] = None,
        output_format: str = "mp3_44100_128",
    ) -> dict:
        """Multi-speaker Text to Dialogue (one unified, conversationally-aware audio).

        USE THIS for any shot where 2+ characters speak/trade lines — NOT concatenated tts() calls.
        APPLY reference/elevenlabs-dialogue-emotion.md (every line tagged, locked settings, etc.).

        turns: list of {"voice": <name|voice_id>, "text": "[tag] line"} in spoken order.
               ≤10 unique voices, ≤2000 chars total.

        Returns {path, request_id, model, voice_ids}.
        """
        inputs = []
        used = []
        for t in turns:
            vid = t["voice"]
            if not (len(vid) == 20 and vid.isalnum()):  # not already a raw voice_id → resolve by name
                vid = self.find_voice_id(vid)
            inputs.append({"voice_id": vid, "text": t["text"]})
            used.append(vid)
        print(f"  → ElevenLabs Dialogue: {len(inputs)} turns, {len(set(used))} voices, model={model_id}")

        body = {
            "inputs": inputs,
            "model_id": model_id,
            "settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True,
            },
        }
        if seed is not None:
            body["seed"] = seed

        r = self.s.post(
            f"{BASE}/text-to-dialogue?output_format={output_format}",
            json=body,
            headers={"Accept": "audio/mpeg"},
        )
        if not r.ok:
            raise ElevenLabsError(f"dialogue → {r.status_code}: {r.text[:400]}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(r.content)

        size_kb = len(r.content) / 1024
        req_id = r.headers.get("request-id", "")
        print(f"  → saved {out_path} ({size_kb:.0f} KB)  request_id={req_id}")

        return {
            "path": str(out_path),
            "request_id": req_id,
            "model": model_id,
            "voice_ids": used,
        }
