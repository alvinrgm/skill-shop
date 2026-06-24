#!/usr/bin/env python3
"""bridge.py — the one place that talks to your deployed gsuite-bridge web app.

Every other script imports `call` / `api` from here, so the URL + secret live in
exactly one place: your `.env`. Nothing is hardcoded.

    .env (next to this package, or exported in your shell):
        GSUITE_BRIDGE_URL=https://script.google.com/macros/s/AKfycb..../exec
        GSUITE_BRIDGE_SECRET=gsb-<your-long-random-string>

Usage from Python:
    import bridge
    bridge.call({"action": "create_doc", "title": "Hello"})
    bridge.api("slides", "GET", f"/v1/presentations/{pid}")          # Slides REST read
    bridge.api("slides", "POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": [...]})

Usage from the shell (quick poke):
    python3 bridge.py '{"action":"list_files","limit":5}'
"""
import json
import os
import sys
import urllib.request

# --- config: read from env, with a tiny .env loader so you don't need python-dotenv ---
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """Load KEY=VALUE lines from a .env in this folder or its parent (package root)."""
    for env_path in (os.path.join(_HERE, ".env"), os.path.join(_HERE, "..", ".env")):
        if not os.path.exists(env_path):
            continue
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

URL = os.environ.get("GSUITE_BRIDGE_URL", "")
SECRET = os.environ.get("GSUITE_BRIDGE_SECRET", "")


def _require_config():
    missing = [k for k, v in (("GSUITE_BRIDGE_URL", URL), ("GSUITE_BRIDGE_SECRET", SECRET)) if not v]
    if missing:
        raise SystemExit(
            "Missing config: " + ", ".join(missing) + ".\n"
            "Set them in a .env at the package root (copy .env.example), or export them.\n"
            "See SETUP.md to deploy the Apps Script and get your /exec URL + secret."
        )


def call(payload: dict, timeout: int = 240) -> dict:
    """POST one action to the bridge. Returns the parsed JSON response."""
    _require_config()
    body = {"secret": SECRET, **payload}
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def api(api_name: str, method: str, path: str, body=None, query=None) -> dict:
    """Call any Docs/Sheets/Slides/Drive REST method through the bridge passthrough.

    api_name: 'docs' | 'sheets' | 'slides' | 'drive'
    Returns the bridge envelope: { success, status, body }.
    """
    payload = {"action": "google_api", "api": api_name, "method": method, "path": path}
    if body is not None:
        payload["body"] = body
    if query is not None:
        payload["query"] = query
    return call(payload)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    print(json.dumps(call(json.loads(sys.argv[1])), indent=2)[:4000])
