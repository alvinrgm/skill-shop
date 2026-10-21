#!/usr/bin/env python3
"""Verify the document bridge: confirms which account it runs as and that it can
create/edit Docs, Sheets, and Slides. Creates throwaway files and trashes them.

Usage:
    python3 verify_bridge.py "<EXEC_URL>" "<SECRET>"

EXEC_URL = the /exec web-app URL from your deployment (see bridge/SETUP.md).
SECRET   = the secret you set in Code.gs (and in your .env). Required.
"""
import json, os, sys, urllib.request


def call(url, secret, payload):
    payload = {"secret": secret, **payload}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=120).read().decode())


def main():
    if len(sys.argv) < 2:
        print("usage: python3 verify_bridge.py <EXEC_URL> <SECRET>"); sys.exit(1)
    url = sys.argv[1]
    secret = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("BRIDGE_SECRET")
    if not secret:
        print("error: pass the bridge SECRET as the 2nd arg or set BRIDGE_SECRET"); sys.exit(1)

    ok = True

    # 1. IDENTITY — which account is this bridge running as?
    who = call(url, secret, {"action": "google_api", "api": "drive", "method": "GET",
                             "path": "/drive/v3/about?fields=user"})
    email = (who.get("body", {}).get("user", {}) or {}).get("emailAddress", "?")
    print(f"[identity] running as: {email}")
    if email == "?":
        print("  !! WARNING: could not read identity — check the URL + secret"); ok = False

    # 2. SLIDES — create a presentation, then trash it
    pres = call(url, secret, {"action": "google_api", "api": "slides", "method": "POST",
                              "path": "/v1/presentations", "body": {"title": "bridge verify — DELETE ME"}})
    pid = pres.get("body", {}).get("presentationId")
    print(f"[slides]   create: {'OK ' + pid if pid else 'FAIL ' + json.dumps(pres)[:200]}")
    if pid:
        call(url, secret, {"action": "delete_file", "fileId": pid})
        print("[slides]   cleaned up")
    else:
        ok = False

    # 3. DOC — core action create_doc, then trash
    doc = call(url, secret, {"action": "create_doc", "title": "bridge verify — DELETE ME",
                             "contentBlocks": [{"type": "heading1", "text": "ok"}]})
    did = doc.get("docId")
    print(f"[docs]     create: {'OK ' + did if did else 'FAIL ' + json.dumps(doc)[:200]}")
    if did:
        call(url, secret, {"action": "delete_file", "fileId": did}); print("[docs]     cleaned up")
    else:
        ok = False

    # 4. SHEET — create_sheet, then trash
    sh = call(url, secret, {"action": "create_sheet", "title": "bridge verify — DELETE ME"})
    sid = sh.get("spreadsheetId") or sh.get("sheetId") or sh.get("id")
    print(f"[sheets]   create: {'OK ' + str(sid) if sid else 'FAIL ' + json.dumps(sh)[:200]}")
    if sid:
        call(url, secret, {"action": "delete_file", "fileId": sid}); print("[sheets]   cleaned up")
    else:
        ok = False

    print("\n" + ("ALL GREEN — bridge is live ✅" if ok else "SOME CHECKS FAILED ❌ — see above"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
