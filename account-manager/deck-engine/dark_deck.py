#!/usr/bin/env python3
"""Dark, dense, diagrammatic deck primitives over your own deployed Apps Script bridge (native
Google Slides, editable, created in the bridge account's Drive). Built after the light deckkit
version was rejected for look/feel.

Palette: near-black bg, slate grey, amber #FFC44D accent (sparing, NOT filled bars).
Everything is custom shapes/text so we can do cards, module grids, and diagrams instead of bullets.
"""
import os, sys, time, json
import urllib.error
# deckkit is vendored alongside this file in deck-engine/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deckkit as dk  # reuse bridge transport (dk.call / dk.api)

# Resilient transport: the Apps Script bridge throws occasional transient 500s. Retry them
# so a single blip doesn't kill a 14-slide build.
_raw_api = dk.api
def _retry_api(method, path, body=None, _tries=5):
    last = None
    for i in range(_tries):
        try:
            r = _raw_api(method, path, body)
        except urllib.error.HTTPError as e:
            if e.code >= 500 and i < _tries - 1:
                time.sleep(1.5 * (i + 1)); continue
            raise
        except Exception:
            if i < _tries - 1:
                time.sleep(1.5 * (i + 1)); continue
            raise
        if isinstance(r, dict) and not r.get("success", True) and i < _tries - 1:
            time.sleep(1.2 * (i + 1)); last = r; continue
        return r
    return last
dk.api = _retry_api

# ---- palette (rgb 0..1): the dark deck template ----
BG       = (0.0902, 0.0980, 0.0941)  # #171918 template master background
SURFACE  = (0.1255, 0.1294, 0.1216)  # #20211F card
SURFACE2 = (0.1647, 0.1686, 0.1569)  # #2A2B28 lighter card
HAIR     = (0.2275, 0.2353, 0.2196)  # #3A3C38 hairline
TEXT     = (1.0, 1.0, 1.0)           # #FFFFFF headings
BODY     = (0.945, 0.945, 0.945)     # #F1F1F1 body text
MUTED    = (0.757, 0.776, 0.792)     # #C1C6CA template muted (cooler/lighter)
AMBER    = (1.0, 0.769, 0.302)       # #FFC44D template accent
AMBERDK  = (0.180, 0.149, 0.082)     # amber-tinted dark fill
GHOST    = (0.231, 0.255, 0.278)     # #3B4147 ghost section numbers
GREEN    = (0.40, 0.85, 0.55)
RED      = (0.96, 0.45, 0.45)
FONT = "Poppins"
PAGE_W, PAGE_H = 9144000, 5143500
EMU_IN = 914400

def rgb(c): return {"rgbColor": {"red": c[0], "green": c[1], "blue": c[2]}}
def emu(v): return {"magnitude": int(v), "unit": "EMU"}
def pt(v): return {"magnitude": v, "unit": "PT"}

class Deck:
    def __init__(self, title):
        r = dk.api("POST", "/v1/presentations", {"title": title})
        self.pid = r["body"]["presentationId"]
        self.first = r["body"]["slides"][0]["objectId"]
        self._seq = 0
        self._used_first = False
        self._strip_placeholders()

    def _strip_placeholders(self):
        """The default first slide inherits CENTERED_TITLE / SUBTITLE placeholders. They render as
        ghostly 'Click to add title/subtitle' prompts in the editor (invisible in the thumbnail
        endpoint, so render-QA misses them) sitting behind our custom text. Delete them on every
        slide so no deck ships with the artifact."""
        try:
            r = dk.api("GET", f"/v1/presentations/{self.pid}?fields=slides(pageElements(objectId,shape(placeholder(type))))")
            reqs = []
            for sl in r["body"]["slides"]:
                for e in sl.get("pageElements", []):
                    if e.get("shape", {}).get("placeholder"):
                        reqs.append({"deleteObject": {"objectId": e["objectId"]}})
            if reqs:
                dk.api("POST", f"/v1/presentations/{self.pid}:batchUpdate", {"requests": reqs})
        except Exception:
            pass  # non-fatal; cover can be cleaned manually if this ever fails

    def uid(self, p="o"):
        self._seq += 1
        return f"{p}{int(time.time()*1000)%100000}{self._seq:04d}"

    def slide(self):
        """Start a new dark slide; returns (sid, reqs-list to append to)."""
        reqs = []
        if not self._used_first:
            sid = self.first
            self._used_first = True
        else:
            sid = self.uid("s")
            reqs.append({"createSlide": {"objectId": sid,
                "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        reqs.append({"updatePageProperties": {"objectId": sid,
            "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": rgb(BG)}}},
            "fields": "pageBackgroundFill.solidFill.color"}})
        return sid, reqs

    def flush(self, reqs):
        time.sleep(0.4)
        r = dk.api("POST", f"/v1/presentations/{self.pid}:batchUpdate", {"requests": reqs})
        if not r.get("success", True):
            raise RuntimeError(json.dumps(r)[:400])
        return r

    # ---- element builders (append requests to `reqs`) ----
    def rect(self, reqs, sid, x, y, w, h, fill=SURFACE, line=HAIR, line_w=1.0, rounded=True):
        oid = self.uid("r")
        reqs.append({"createShape": {"objectId": oid,
            "shapeType": "ROUND_RECTANGLE" if rounded else "RECTANGLE",
            "elementProperties": {"pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x), "translateY": int(y), "unit": "EMU"}}}})
        sp = {"fields": "", "shapeProperties": {}}
        fields = []
        if fill is not None:
            sp["shapeProperties"]["shapeBackgroundFill"] = {"solidFill": {"color": rgb(fill)}}
            fields.append("shapeBackgroundFill.solidFill.color")
        if line is not None:
            sp["shapeProperties"]["outline"] = {"outlineFill": {"solidFill": {"color": rgb(line)}},
                "weight": pt(line_w), "dashStyle": "SOLID"}
            fields.append("outline")
        else:
            sp["shapeProperties"]["outline"] = {"propertyState": "NOT_RENDERED"}
            fields.append("outline.propertyState")
        sp["fields"] = ",".join(fields)
        sp["objectId"] = oid
        reqs.append({"updateShapeProperties": sp})
        return oid

    def text(self, reqs, sid, x, y, w, h, runs, size=11, color=TEXT, bold=False, align="START",
             spacing=100, valign=None, caps=False, tracking=None, italic=False):
        """runs = string, or list of (text, style-overrides dict)."""
        oid = self.uid("t")
        reqs.append({"createShape": {"objectId": oid, "shapeType": "TEXT_BOX",
            "elementProperties": {"pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x), "translateY": int(y), "unit": "EMU"}}}})
        reqs.append({"updateShapeProperties": {"objectId": oid,
            "shapeProperties": {"autofit": {"autofitType": "NONE"},
                **({"contentAlignment": valign} if valign else {})},
            "fields": "autofit.autofitType" + (",contentAlignment" if valign else "")}})
        if isinstance(runs, str):
            runs = [(runs, {})]
        full = "".join(t for t, _ in runs)
        if caps:
            full = full.upper()
        reqs.append({"insertText": {"objectId": oid, "text": full}})
        # base style on all
        base = {"fontSize": pt(size), "foregroundColor": {"opaqueColor": rgb(color)},
                "bold": bold, "italic": italic, "weightedFontFamily": {"fontFamily": FONT}}
        if tracking is not None:
            pass  # letter spacing not supported per-run reliably; emulate caps look via spaces if needed
        reqs.append({"updateTextStyle": {"objectId": oid, "style": base, "textRange": {"type": "ALL"},
            "fields": "fontSize,foregroundColor,bold,italic,weightedFontFamily"}})
        # per-run overrides
        idx = 0
        for t, ov in runs:
            seg = t.upper() if caps else t
            s0, e0 = idx, idx + len(seg)
            if ov:
                st = {"weightedFontFamily": {"fontFamily": FONT}}
                f = ["weightedFontFamily"]
                if "size" in ov: st["fontSize"] = pt(ov["size"]); f.append("fontSize")
                if "color" in ov: st["foregroundColor"] = {"opaqueColor": rgb(ov["color"])}; f.append("foregroundColor")
                if "bold" in ov: st["bold"] = ov["bold"]; f.append("bold")
                if "italic" in ov: st["italic"] = ov["italic"]; f.append("italic")
                reqs.append({"updateTextStyle": {"objectId": oid, "style": st,
                    "textRange": {"type": "FIXED_RANGE", "startIndex": s0, "endIndex": e0}, "fields": ",".join(f)}})
            idx = e0
        reqs.append({"updateParagraphStyle": {"objectId": oid,
            "style": {"alignment": align, "lineSpacing": spacing},
            "textRange": {"type": "ALL"}, "fields": "alignment,lineSpacing"}})
        return oid

    def image(self, reqs, sid, url, x, y, w, h):
        oid = self.uid("img")
        reqs.append({"createImage": {"objectId": oid, "url": url,
            "elementProperties": {"pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x), "translateY": int(y), "unit": "EMU"}}}})
        return oid

    def arrow(self, reqs, sid, x, y, w, h, fill=AMBER):
        oid = self.uid("ar")
        reqs.append({"createShape": {"objectId": oid, "shapeType": "RIGHT_ARROW",
            "elementProperties": {"pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x), "translateY": int(y), "unit": "EMU"}}}})
        reqs.append({"updateShapeProperties": {"objectId": oid,
            "shapeProperties": {"shapeBackgroundFill": {"solidFill": {"color": rgb(fill)}},
                "outline": {"propertyState": "NOT_RENDERED"}},
            "fields": "shapeBackgroundFill.solidFill.color,outline.propertyState"}})
        return oid

    def glow(self, reqs, sid, x, y, w, h, color=AMBER, alpha=0.08, oval=True):
        """Low-alpha soft wash — the closest Google Slides gets to the skill's 'atmosphere over
        solid color' principle (no real blur in Slides). Add BEFORE other elements so it sits behind."""
        oid = self.uid("g")
        reqs.append({"createShape": {"objectId": oid, "shapeType": "ELLIPSE" if oval else "RECTANGLE",
            "elementProperties": {"pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x), "translateY": int(y), "unit": "EMU"}}}})
        reqs.append({"updateShapeProperties": {"objectId": oid,
            "shapeProperties": {"shapeBackgroundFill": {"solidFill": {"color": rgb(color), "alpha": alpha}},
                "outline": {"propertyState": "NOT_RENDERED"}},
            "fields": "shapeBackgroundFill.solidFill.color,shapeBackgroundFill.solidFill.alpha,outline.propertyState"}})
        return oid

    def render(self, index, out):
        import urllib.request
        ids = [s["objectId"] for s in dk.api("GET", f"/v1/presentations/{self.pid}?fields=slides.objectId")["body"]["slides"]]
        last = None
        for attempt in range(5):  # thumbnail endpoint throws occasional transient 502s
            try:
                tr = dk.api("GET", f"/v1/presentations/{self.pid}/pages/{ids[index]}/thumbnail?thumbnailProperties.mimeType=PNG&thumbnailProperties.thumbnailSize=LARGE")
                cu = (tr or {}).get("body", {}).get("contentUrl")
                if cu:
                    urllib.request.urlretrieve(cu, out)
                    return out
            except Exception as e:
                last = e
            time.sleep(1.3 * (attempt + 1))
        if last:
            raise last
        return out
