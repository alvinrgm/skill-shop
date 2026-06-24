#!/usr/bin/env python3
"""deckkit — reusable Google Slides building primitives over the bridge.

Style-spec driven: pass a spec from extract_style.py (or hand-write one) and every
slide it builds inherits that deck's font, colors, and sizes — so new slides MATCH
the look you extracted. With no spec, it falls back to neutral defaults that track
the template's theme.

⛔ GOLDEN RULE: create_deck / wipe_slides are FIRST-BUILD ONLY. Once a deck exists and
a human may have edited it, use ONLY the granular add_* helpers (for new slides) and
apply_style / updateTextStyle (for edits). NEVER wipe-and-recreate a live deck — it
destroys human edits.

Usage (first build):
    import deckkit as dk, json
    st  = dk.Style(json.load(open("brand.json")))     # from extract_style.py; or dk.Style({})
    pid = dk.copy_template(TEMPLATE_ID, "Acme Deck")   # inherit a themed template
    dk.wipe_slides(pid)                                # only on the fresh copy
    dk.add_cover(pid, "Q3 Plan", "Acme · 2026", st, logo_url=LOGO)
    dk.add_text_slide(pid, 1, "Context", [("h","Today"),("b","point one")], st)
    dk.add_table_slide(pid, 2, "Demand", ["Term","Vol"], [["paint","1k"]], st, subtitle="...")
    dk.set_autofit_none(pid)                           # uniform body sizing
    dk.render(pid, 0, "/tmp/cover.png")                # screenshot a slide to verify
"""
import json
import sys
import time
import urllib.request

import bridge
import gslib

PAGE_W, PAGE_H = 9144000, 5143500   # default 16:9 in EMU; overridden by spec.page_size
_seq = [0]


def _uid(p):
    _seq[0] += 1
    return f"{p}{int(time.time() * 1000) % 100000}{_seq[0]:03d}"


def api(method, path, body=None):
    return bridge.api("slides", method, path, body)


class Style:
    """Resolves a style spec into ready-to-use font/color/size values, with fallbacks.

    Pass the dict from extract_style.py. Any missing field falls back to a neutral
    default that reads well on most templates.
    """

    def __init__(self, spec=None):
        spec = spec or {}
        self.spec = spec
        self.font = (spec.get("fonts") or {}).get("primary")   # None = template default
        ps = spec.get("page_size")
        if ps and ps.get("width") and ps.get("height"):
            self.page_w = ps["width"].get("magnitude", PAGE_W)
            self.page_h = ps["height"].get("magnitude", PAGE_H)
        else:
            self.page_w, self.page_h = PAGE_W, PAGE_H

    def _role(self, role, default_size, default_hex):
        r = self.spec.get(role) or {}
        size = r.get("size_pt", default_size)
        color_hex = r.get("color", default_hex)
        return size, color_hex

    def text_style(self, role, default_size, default_hex, bold=None, italic=None):
        """Return a Slides textRun style dict + fields list for a given role."""
        r = self.spec.get(role) or {}
        size = r.get("size_pt", default_size)
        color_hex = r.get("color", default_hex)
        style, fields = {}, []
        if self.font:
            gslib.font(style, self.font)
            fields.append("weightedFontFamily")
        style["fontSize"] = gslib.pt(size)
        fields.append("fontSize")
        style["foregroundColor"] = gslib.opaque(color_hex)
        fields.append("foregroundColor")
        b = r.get("bold") if bold is None else bold
        if b is not None:
            style["bold"] = bool(b)
            fields.append("bold")
        it = r.get("italic") if italic is None else italic
        if it is not None:
            style["italic"] = bool(it)
            fields.append("italic")
        return style, ",".join(fields)

    def table_header_fill(self, default_hex="#1A1A1A"):
        return (self.spec.get("table_header") or {}).get("fill", default_hex)


# ---- template / structure ----
def copy_template(template_id, name):
    """Duplicate a themed master deck. Returns new presentationId (inherits theme + layouts)."""
    r = bridge.call({"action": "copy_file", "fileId": template_id, "name": name})
    return r.get("newFileId") or r.get("fileId") or r.get("id")


def create_deck(name):
    """Create a BLANK presentation (default theme). FIRST-BUILD ONLY. Returns presentationId."""
    r = api("POST", "/v1/presentations", {"title": name})
    return r.get("body", {}).get("presentationId")


def slide_ids(pid):
    return [s["objectId"] for s in api("GET", f"/v1/presentations/{pid}?fields=slides.objectId")["body"]["slides"]]


def wipe_slides(pid):
    """FIRST-BUILD ONLY. Delete all slides on a freshly-copied template before building."""
    ids = slide_ids(pid)
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests":
        [{"createSlide": {"objectId": "tmp_wipe0", "insertionIndex": len(ids)}}]
        + [{"deleteObject": {"objectId": o}} for o in ids]})
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": [{"deleteObject": {"objectId": "tmp_wipe0"}}]})


def theme(pid):
    """Return {layouts: {displayName: id}, colors: colorScheme} for a deck/template."""
    d = api("GET", f"/v1/presentations/{pid}?fields=layouts(objectId,layoutProperties.displayName),masters(pageProperties(colorScheme))")["body"]
    lay = {L.get("layoutProperties", {}).get("displayName", "?"): L["objectId"] for L in d.get("layouts", [])}
    return {"layouts": lay, "colors": d.get("masters", [{}])[0].get("pageProperties", {}).get("colorScheme", {})}


# ---- slide builders ----
def add_cover(pid, title, subtitle, st, logo_url=None, layout="BLANK"):
    sid, tid, subid = _uid("cov"), _uid("covT"), _uid("covS")
    reqs = [{"createSlide": {"objectId": sid, "insertionIndex": 0,
                             "slideLayoutReference": {"predefinedLayout": layout}}}]
    if logo_url:
        lw = 1400000
        reqs.append({"createImage": {"objectId": _uid("logo"), "url": logo_url, "elementProperties": {"pageObjectId": sid,
            "size": {"width": gslib.emu(lw), "height": gslib.emu(lw)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": (st.page_w - lw) // 2, "translateY": 380000, "unit": "EMU"}}}})
    tstyle, tfields = st.text_style("title", 36, "#1A1A1A", bold=True)
    sstyle, sfields = st.text_style("subtitle", 14, "#5A5A5A")
    reqs += [
        {"createShape": {"objectId": tid, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": gslib.emu(8000000), "height": gslib.emu(1200000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 572000, "translateY": 2150000, "unit": "EMU"}}}},
        {"insertText": {"objectId": tid, "text": title}},
        {"updateTextStyle": {"objectId": tid, "style": tstyle, "textRange": {"type": "ALL"}, "fields": tfields}},
        {"updateParagraphStyle": {"objectId": tid, "style": {"alignment": "CENTER"}, "textRange": {"type": "ALL"}, "fields": "alignment"}},
        {"createShape": {"objectId": subid, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": gslib.emu(8000000), "height": gslib.emu(700000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 572000, "translateY": 3520000, "unit": "EMU"}}}},
        {"insertText": {"objectId": subid, "text": subtitle}},
        {"updateTextStyle": {"objectId": subid, "style": sstyle, "textRange": {"type": "ALL"}, "fields": sfields}},
        {"updateParagraphStyle": {"objectId": subid, "style": {"alignment": "CENTER"}, "textRange": {"type": "ALL"}, "fields": "alignment"}},
    ]
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})
    return sid


def add_text_slide(pid, index, title, items, st, subtitle=None, layout="TITLE_AND_BODY"):
    """items = list of ('h', text) headings | ('b', text) bullets. Headings render bold (no bullet)."""
    sid, tid, bid = _uid("s"), _uid("t"), _uid("b")
    tstyle, tfields = st.text_style("title", 24, "#1A1A1A", bold=True)
    bstyle, bfields = st.text_style("body", 12, "#333333")
    reqs = [{"createSlide": {"objectId": sid, "insertionIndex": index,
        "slideLayoutReference": {"predefinedLayout": layout},
        "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid},
                                  {"layoutPlaceholder": {"type": "BODY", "index": 0}, "objectId": bid}]}},
        {"insertText": {"objectId": tid, "text": title}},
        {"updateTextStyle": {"objectId": tid, "style": tstyle, "textRange": {"type": "ALL"}, "fields": tfields}}]
    body = ("" if not subtitle else subtitle + "\n") + "\n".join(it[1] for it in items)
    reqs.append({"insertText": {"objectId": bid, "text": body}})
    reqs.append({"updateShapeProperties": {"objectId": bid, "shapeProperties": {"autofit": {"autofitType": "NONE"}}, "fields": "autofit.autofitType"}})
    reqs.append({"updateTextStyle": {"objectId": bid, "style": bstyle, "textRange": {"type": "ALL"}, "fields": bfields}})
    if subtitle:
        sub_style, _ = st.text_style("subtitle", 11, "#777777", italic=True)
        reqs.append({"updateTextStyle": {"objectId": bid, "style": sub_style,
            "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": len(subtitle)},
            "fields": "italic,fontSize,foregroundColor"}})
    off = (len(subtitle) + 1) if subtitle else 0
    groups, cur = [], None
    for kind, text in items:
        s0, e0 = off, off + len(text)
        if kind == "h":
            reqs.append({"updateTextStyle": {"objectId": bid, "style": {"bold": True},
                "textRange": {"type": "FIXED_RANGE", "startIndex": s0, "endIndex": e0}, "fields": "bold"}})
            reqs.append({"updateParagraphStyle": {"objectId": bid, "style": {"spaceAbove": gslib.pt(6)},
                "textRange": {"type": "FIXED_RANGE", "startIndex": s0, "endIndex": e0}, "fields": "spaceAbove"}})
            if cur:
                groups.append(cur); cur = None
        else:
            cur = [s0, e0] if cur is None else [cur[0], e0]
        off = e0 + 1
    if cur:
        groups.append(cur)
    for g in groups:
        reqs.append({"createParagraphBullets": {"objectId": bid,
            "textRange": {"type": "FIXED_RANGE", "startIndex": g[0], "endIndex": g[1]},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})
    return sid


def add_callout(pid, slide_id, text, st, fill_hex="#2A2A2A", y=4360000):
    """A shaded crystallization callout near the bottom of a slide."""
    box = _uid("cry")
    cstyle, cfields = st.text_style("title", 13, "#FFFFFF", bold=True)
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": [
        {"createShape": {"objectId": box, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": slide_id,
            "size": {"width": gslib.emu(8300000), "height": gslib.emu(640000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": y, "unit": "EMU"}}}},
        {"updateShapeProperties": {"objectId": box, "shapeProperties": {"shapeBackgroundFill": {"solidFill": gslib.solid(fill_hex)}, "contentAlignment": "MIDDLE"},
            "fields": "shapeBackgroundFill.solidFill.color,contentAlignment"}},
        {"insertText": {"objectId": box, "text": text}},
        {"updateTextStyle": {"objectId": box, "style": cstyle, "textRange": {"type": "ALL"}, "fields": cfields}},
        {"updateParagraphStyle": {"objectId": box, "style": {"alignment": "CENTER"}, "textRange": {"type": "ALL"}, "fields": "alignment"}}]})
    return box


def add_table_slide(pid, index, title, headers, rows, st, subtitle=None, caption=None, layout="TITLE_ONLY"):
    """caption = (text, [(substr,url),...]) or None. rows = list of list[str]; empty cells skipped."""
    sid, tid, tbl = _uid("s"), _uid("t"), _uid("tb")
    ncol, nrow = len(headers), len(rows) + 1
    tstyle, tfields = st.text_style("title", 24, "#1A1A1A", bold=True)
    reqs = [{"createSlide": {"objectId": sid, "insertionIndex": index,
        "slideLayoutReference": {"predefinedLayout": layout},
        "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid}]}},
        {"insertText": {"objectId": tid, "text": title}},
        {"updateTextStyle": {"objectId": tid, "style": tstyle, "textRange": {"type": "ALL"}, "fields": tfields}}]
    ty = 1250000
    if subtitle:
        sb = _uid("sub")
        sub_style, sub_fields = st.text_style("subtitle", 11, "#777777", italic=True)
        reqs += [{"createShape": {"objectId": sb, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": gslib.emu(8300000), "height": gslib.emu(380000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": 1080000, "unit": "EMU"}}}},
            {"insertText": {"objectId": sb, "text": subtitle}},
            {"updateTextStyle": {"objectId": sb, "style": sub_style, "textRange": {"type": "ALL"}, "fields": sub_fields}}]
        ty = 1560000
    reqs.append({"createTable": {"objectId": tbl, "elementProperties": {"pageObjectId": sid,
        "size": {"width": gslib.emu(8300000), "height": gslib.emu(min(2900000, nrow * 420000))},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": ty, "unit": "EMU"}}, "rows": nrow, "columns": ncol}})
    reqs.append({"updateTableCellProperties": {"objectId": tbl, "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": ncol},
        "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": gslib.solid(st.table_header_fill())}}, "fields": "tableCellBackgroundFill.solidFill.color"}})
    hstyle, hfields = st.text_style("table_header", 9, "#FFFFFF", bold=True)
    cstyle, cfields = st.text_style("table_body", 9, "#333333")
    for c, h in enumerate(headers):
        reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": 0, "columnIndex": c}, "text": h}})
        reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": 0, "columnIndex": c},
            "style": hstyle, "textRange": {"type": "ALL"}, "fields": hfields}})
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            if val == "" or val is None:
                continue
            reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c}, "text": str(val)}})
            reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c},
                "style": cstyle, "textRange": {"type": "ALL"}, "fields": cfields}})
    if caption:
        txt, links = caption
        cap = _uid("cap")
        cap_style, cap_fields = st.text_style("subtitle", 8, "#777777", italic=True)
        reqs += [{"createShape": {"objectId": cap, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": gslib.emu(8300000), "height": gslib.emu(360000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": 4760000, "unit": "EMU"}}}},
            {"insertText": {"objectId": cap, "text": txt}},
            {"updateTextStyle": {"objectId": cap, "style": cap_style, "textRange": {"type": "ALL"}, "fields": cap_fields}}]
        for sub, u in (links or []):
            i = txt.find(sub)
            if i >= 0:
                reqs.append({"updateTextStyle": {"objectId": cap, "style": {"link": {"url": u}, "underline": True,
                    "foregroundColor": gslib.opaque("#1A56A6")},
                    "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i + len(sub)}, "fields": "link,underline,foregroundColor"}})
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})
    return sid


def render(pid, index, out_path):
    """Save a PNG thumbnail of slide `index` to out_path — your visual check."""
    ids = slide_ids(pid)
    tr = api("GET", f"/v1/presentations/{pid}/pages/{ids[index]}/thumbnail?thumbnailProperties.mimeType=PNG&thumbnailProperties.thumbnailSize=LARGE")
    cu = tr.get("body", {}).get("contentUrl")
    if cu:
        urllib.request.urlretrieve(cu, out_path)
    return out_path


def set_autofit_none(pid):
    """Disable shrink-on-overflow on every BODY so identical font sizes render uniformly. Safe to re-run."""
    d = api("GET", f"/v1/presentations/{pid}?fields=slides(pageElements(objectId,shape(placeholder(type))))")["body"]
    reqs = []
    for s in d["slides"]:
        for e in s.get("pageElements", []):
            if (e.get("shape", {}).get("placeholder") or {}).get("type") == "BODY":
                reqs.append({"updateShapeProperties": {"objectId": e["objectId"], "shapeProperties": {"autofit": {"autofitType": "NONE"}}, "fields": "autofit.autofitType"}})
    if reqs:
        api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})


if __name__ == "__main__":
    print(__doc__)
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        json.dumps(Style({}).text_style("title", 24, "#000000"))  # smoke
        print("deckkit import + Style OK")
