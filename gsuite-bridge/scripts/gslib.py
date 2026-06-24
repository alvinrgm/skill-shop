#!/usr/bin/env python3
"""gslib — tiny shared primitives for the Slides REST API (colors, units, fonts).

Used by extract_style.py, apply_style.py, and deckkit.py so color/size handling
is identical everywhere. No network here — just pure helpers.
"""

# Standard Slides theme-color slot names, in the order the API returns them.
THEME_SLOTS = [
    "DARK1", "LIGHT1", "DARK2", "LIGHT2",
    "ACCENT1", "ACCENT2", "ACCENT3", "ACCENT4", "ACCENT5", "ACCENT6",
    "HYPERLINK",
]


def pt(v):
    """A PT magnitude object for the Slides API."""
    return {"magnitude": v, "unit": "PT"}


def emu(v):
    return {"magnitude": v, "unit": "EMU"}


def rgb_to_hex(rgb):
    """{'red':0.1,'green':0.2,'blue':0.3} (0-1 floats, missing = 0) -> '#RRGGBB'."""
    if not isinstance(rgb, dict):
        return None
    r = round(255 * rgb.get("red", 0))
    g = round(255 * rgb.get("green", 0))
    b = round(255 * rgb.get("blue", 0))
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


def hex_to_rgb(hex_str):
    """'#RRGGBB' (or 'RRGGBB') -> {'red','green','blue'} in 0-1 floats."""
    if not hex_str:
        return None
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return None
    return {
        "red": int(h[0:2], 16) / 255.0,
        "green": int(h[2:4], 16) / 255.0,
        "blue": int(h[4:6], 16) / 255.0,
    }


def opaque(hex_str):
    """A foregroundColor.opaqueColor object from a hex string."""
    return {"opaqueColor": {"rgbColor": hex_to_rgb(hex_str)}}


def solid(hex_str):
    """A solidFill color object from a hex string."""
    return {"color": {"rgbColor": hex_to_rgb(hex_str)}}


def font(style, family):
    """Add weightedFontFamily to a text style dict (in place) and return it."""
    if family:
        style["weightedFontFamily"] = {"fontFamily": family}
    return style


def color_from_opaque(opaque_color, theme_map):
    """Resolve a Slides opaqueColor ({rgbColor}|{themeColor}) to a hex string.

    theme_map: {slot_name: hex} from the master color scheme, used to resolve
    themeColor refs to concrete hex.
    """
    if not isinstance(opaque_color, dict):
        return None
    if "rgbColor" in opaque_color:
        return rgb_to_hex(opaque_color["rgbColor"])
    if "themeColor" in opaque_color:
        return (theme_map or {}).get(opaque_color["themeColor"])
    return None


def parse_color_scheme(color_scheme):
    """masters[0].pageProperties.colorScheme -> {slot_name: hex}."""
    out = {}
    for c in (color_scheme or {}).get("colors", []):
        slot = c.get("type")
        rgb = c.get("color", {}).get("rgbColor", {})
        if slot:
            out[slot] = rgb_to_hex(rgb)
    return out
