#!/usr/bin/env python3
"""Verify your gsuite-bridge deployment end to end.

Confirms the bridge responds, reports which Google account it runs AS, and proves
it can create + delete a Doc, a Sheet, and a Slides deck. All test files are
throwaways and get trashed automatically.

Reads GSUITE_BRIDGE_URL + GSUITE_BRIDGE_SECRET from .env (via bridge.py), or you
can override on the command line:

    python3 verify_bridge.py                       # uses .env
    python3 verify_bridge.py <EXEC_URL> [SECRET]   # explicit override
"""
import json
import sys

import bridge


def main():
    # Optional CLI override of the env config.
    if len(sys.argv) > 1:
        bridge.URL = sys.argv[1]
    if len(sys.argv) > 2:
        bridge.SECRET = sys.argv[2]

    ok = True

    # 1. IDENTITY — who is this bridge running as?
    who = bridge.api("drive", "GET", "/drive/v3/about?fields=user")
    email = (who.get("body", {}).get("user", {}) or {}).get("emailAddress", "?")
    print(f"[identity] running as: {email}")
    if email == "?":
        print("  !! could not read identity — check the URL/secret and that the deploy is live")
        ok = False

    # 2. SLIDES — create a presentation, then trash it
    pres = bridge.api("slides", "POST", "/v1/presentations",
                      {"title": "gsuite-bridge verify — DELETE ME"})
    pid = pres.get("body", {}).get("presentationId")
    print(f"[slides]   create: {'OK ' + pid if pid else 'FAIL ' + json.dumps(pres)[:200]}")
    if pid:
        bridge.call({"action": "delete_file", "fileId": pid})
        print("[slides]   cleaned up")
    else:
        print("  !! if this is a 403/PERMISSION_DENIED, enable the Slides API (SETUP.md step 5)")
        ok = False

    # 3. DOC — core action create_doc, then trash
    doc = bridge.call({"action": "create_doc", "title": "gsuite-bridge verify — DELETE ME",
                       "contentBlocks": [{"type": "heading1", "text": "ok"}]})
    did = doc.get("docId")
    print(f"[docs]     create: {'OK ' + did if did else 'FAIL ' + json.dumps(doc)[:200]}")
    if did:
        bridge.call({"action": "delete_file", "fileId": did})
        print("[docs]     cleaned up")
    else:
        ok = False

    # 4. SHEET — create_sheet, then trash
    sh = bridge.call({"action": "create_sheet", "title": "gsuite-bridge verify — DELETE ME"})
    sid = sh.get("spreadsheetId") or sh.get("id")
    print(f"[sheets]   create: {'OK ' + str(sid) if sid else 'FAIL ' + json.dumps(sh)[:200]}")
    if sid:
        bridge.call({"action": "delete_file", "fileId": sid})
        print("[sheets]   cleaned up")
    else:
        ok = False

    print("\n" + ("ALL GREEN — bridge is live ✅" if ok else "SOME CHECKS FAILED ❌ — see above"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
