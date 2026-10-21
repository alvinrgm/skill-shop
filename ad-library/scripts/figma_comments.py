#!/usr/bin/env python3
"""Read and answer the comments people leave on the brand's Figma file (Figma REST API).

Comments are how reviewers talk to the library ("headline too small", "use the new pack").
Every session starts by reading the open ones, and every comment gets a reply once it is acted on.
This uses a Figma personal access token (your own), not the MCP, because the MCP has no comment
tools.

usage:
  figma_comments.py list  <brand> [--all]          open top-level comments + their replies (JSON)
  figma_comments.py reply <brand> <comment_id> "message"
  figma_comments.py pending <brand>                open comments with no reply from you yet

Each comment carries client_meta: often node_id is the PAGE root, so use node_offset against the
root's layout to find which card or ad it sits on. Replies are prefixed "claude: " by default
(set FIGMA_REPLY_PREFIX to change it) so humans can tell them apart. Resolving is done in the
Figma UI (the REST API cannot resolve), once the fix is live.

Env: FIGMA_TOKEN (Figma > Settings > Security > Personal access tokens, scopes
file_comments:read + file_comments:write, plus file_content:read). The file key comes from
<brand>/state.json (file_key).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brand_dir  # noqa: E402

API = "https://api.figma.com/v1"


def call(method: str, path: str, body: dict | None = None) -> dict:
    tok = os.environ.get("FIGMA_TOKEN", "").strip()
    if not tok:
        sys.exit("FIGMA_TOKEN is not set (see SETUP.md, 'Figma comments').")
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"X-Figma-Token": tok, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Figma API HTTP {e.code}: {e.read().decode()[:300]}")


def file_key(brand: str) -> str:
    st = json.loads((brand_dir(brand) / "state.json").read_text())
    k = st.get("file_key", "")
    if not k or k.startswith("YOUR_"):
        sys.exit("state.json has no file_key yet (ONBOARD creates the file and records it).")
    return k


def threads(brand: str, include_resolved: bool) -> list[dict]:
    cs = call("GET", f"/files/{file_key(brand)}/comments").get("comments", [])
    tops = {c["id"]: dict(c, replies=[]) for c in cs if not c.get("parent_id")}
    for c in cs:
        if c.get("parent_id") in tops:
            tops[c["parent_id"]]["replies"].append(c)
    out = []
    for c in sorted(tops.values(), key=lambda x: x["created_at"]):
        if c.get("resolved_at") and not include_resolved:
            continue
        out.append({"id": c["id"], "by": c.get("user", {}).get("handle"), "at": c["created_at"],
                    "message": c.get("message"), "client_meta": c.get("client_meta"),
                    "resolved": bool(c.get("resolved_at")),
                    "replies": [{"by": r.get("user", {}).get("handle"), "message": r.get("message"),
                                 "at": r["created_at"]} for r in c["replies"]]})
    return out


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, brand = sys.argv[1], sys.argv[2]
    prefix = os.environ.get("FIGMA_REPLY_PREFIX", "claude: ")
    if cmd == "list":
        print(json.dumps(threads(brand, "--all" in sys.argv), indent=1, ensure_ascii=False))
    elif cmd == "pending":
        p = [t for t in threads(brand, False) if not any(r["message"].startswith(prefix) for r in t["replies"])]
        print(json.dumps(p, indent=1, ensure_ascii=False))
        print(f"{len(p)} open comments without a reply", file=sys.stderr)
    elif cmd == "reply" and len(sys.argv) >= 5:
        msg = sys.argv[4] if sys.argv[4].startswith(prefix) else prefix + sys.argv[4]
        r = call("POST", f"/files/{file_key(brand)}/comments", {"message": msg, "comment_id": sys.argv[3]})
        print(f"replied ({r.get('id')})")
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
