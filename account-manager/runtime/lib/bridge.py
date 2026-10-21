"""Apps Script bridge client — Slides / Sheets / Drive via your own deployed bridge.

All Google writes for the AI Account Manager go through the Apps Script bridge
(see bridge/SETUP.md). This module wraps the HTTP contract. It reads the bridge
exec URL + secret from the package .env (BRIDGE_URL / BRIDGE_SECRET).
"""
import json
import os
import time
import urllib.request

_ENV = {}


def _load_env():
    if _ENV:
        return _ENV
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    path = os.path.abspath(path)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            _ENV[k.strip()] = v.strip()
    return _ENV


def _url_secret():
    e = _load_env()
    return e["BRIDGE_URL"], e["BRIDGE_SECRET"]


def call(action, timeout=180, **payload):
    """POST one action to the bridge. Returns parsed JSON dict. Raises on transport error."""
    url, secret = _url_secret()
    payload["action"] = action
    payload["secret"] = secret
    data = json.dumps(payload).encode()
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
            return json.loads(raw)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"bridge call '{action}' failed after retries: {last}")


# ---- Google API passthrough helpers -------------------------------------

def gapi(api, path, method="GET", query=None, body=None, timeout=180):
    """Raw Google API passthrough. Returns the parsed `body` of the API response.

    The bridge returns {success, status, body}; body may be a JSON string for
    large responses — we parse it. Raises RuntimeError on non-2xx.
    """
    r = call("google_api", api=api, path=path, method=method,
             query=query or {}, body=body, timeout=timeout)
    if not r.get("success"):
        raise RuntimeError(f"gapi {method} {path} -> {r.get('status')}: {str(r.get('body'))[:400]}")
    b = r.get("body")
    if isinstance(b, str):
        b = json.loads(b)
    return b


# ---- Slides --------------------------------------------------------------

def slides_get(presentation_id, fields=None):
    q = {"fields": fields} if fields else {}
    return gapi("slides", f"/v1/presentations/{presentation_id}", query=q)


def slides_page(presentation_id, page_object_id):
    return gapi("slides", f"/v1/presentations/{presentation_id}/pages/{page_object_id}")


def slides_batch(presentation_id, requests):
    """Apply a slides batchUpdate. `requests` is the list of request dicts."""
    return gapi("slides", f"/v1/presentations/{presentation_id}:batchUpdate",
                method="POST", body={"requests": requests})


def slide_object_ids(presentation_id):
    """Return ordered list of slide objectIds (cheap, fields-masked)."""
    b = slides_get(presentation_id, fields="slides.objectId")
    return [s["objectId"] for s in b.get("slides", [])]


# ---- Sheets --------------------------------------------------------------

def sheet_meta(spreadsheet_id):
    b = gapi("sheets", f"/v4/spreadsheets/{spreadsheet_id}",
             query={"fields": "properties.title,sheets.properties(title,gridProperties(rowCount,columnCount))"})
    return b


def sheet_values(spreadsheet_id, a1_range):
    b = gapi("sheets", f"/v4/spreadsheets/{spreadsheet_id}/values/{a1_range}")
    return b.get("values", [])


def sheets_batch(spreadsheet_id, requests):
    return gapi("sheets", f"/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
                method="POST", body={"requests": requests})


# ---- Drive ---------------------------------------------------------------

def drive_file_modified(file_id):
    """Return RFC3339 modifiedTime for a Drive file."""
    b = gapi("drive", f"/drive/v3/files/{file_id}",
             query={"fields": "modifiedTime,name", "supportsAllDrives": "true"})
    return b


def copy_file(file_id, new_name):
    """Copy a Drive file (used to make a safe staging copy of a deck)."""
    return call("copy_file", fileId=file_id, name=new_name)
