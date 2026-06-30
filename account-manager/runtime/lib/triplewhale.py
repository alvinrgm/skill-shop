"""Triple Whale client — the NC-ROAS / blended-attribution source for reporting.

The working contract (found by live probing):
  POST https://api.triplewhale.com/api/v2/summary-page/get-data
  headers: {"x-api-key": <key>}
  body:    {"shopDomain": "<x>.myshopify.com", "period": {"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}}
Returns ~700 metrics, each with values.current / values.previous + delta + daily charts.
(`shopId`/`shop` -> 403; the field is `shopDomain`. `period` is REQUIRED as an object.)

Key: TRIPLEWHALE_API_KEY in the package .env. Shop domain: per-client account.md
(`tw_shop_domain`), e.g. example-brand.myshopify.com.

Headline metricIds used in reporting:
  totalRoas (Blended ROAS), newCustomersRoas (New Customer ROAS),
  blendedAttributedRoas, mer, newCustomersCpa, totalCpa (Blended CPA),
  newCustomersPercent, shopifyAov (AOV), blendedAds (Blended Ad Spend),
  totalSales (Order Revenue), newCustomerSales (New Customer Revenue),
  ga_ROAS (Google ROAS), fb_ads_purchase_roas (Facebook ROAS).
"""
import json
import os
import urllib.request

BASE = "https://api.triplewhale.com/api/v2"

HEADLINE = {
    "totalRoas": "Blended ROAS", "newCustomersRoas": "New Customer ROAS",
    "blendedAttributedRoas": "Blended Attributed ROAS", "mer": "MER",
    "newCustomersCpa": "New Customer CPA", "totalCpa": "Blended CPA",
    "newCustomersPercent": "New Customers %", "shopifyAov": "AOV",
    "blendedAds": "Blended Ad Spend", "totalSales": "Order Revenue",
    "newCustomerSales": "New Customer Revenue", "ga_ROAS": "Google ROAS",
    "fb_ads_purchase_roas": "Facebook ROAS",
}


def _key():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    with open(path) as f:
        for line in f:
            if line.startswith("TRIPLEWHALE_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("TRIPLEWHALE_API_KEY missing from .env")


def summary(shop_domain, start, end):
    """Pull the Summary Page for a period. Returns the parsed dict (raises on non-200)."""
    req = urllib.request.Request(
        BASE + "/summary-page/get-data",
        data=json.dumps({"shopDomain": shop_domain, "period": {"start": start, "end": end}}).encode(),
        headers={"Content-Type": "application/json", "x-api-key": _key()}, method="POST")
    resp = urllib.request.urlopen(req, timeout=90)
    return json.loads(resp.read().decode())


def metrics(shop_domain, start, end, ids=None):
    """Return {metricId: {title, current, previous, delta}} for the requested ids
    (defaults to the HEADLINE set)."""
    data = summary(shop_domain, start, end)
    by_id = {m.get("metricId"): m for m in data.get("metrics", [])}
    ids = ids or list(HEADLINE)
    out = {}
    for mid in ids:
        m = by_id.get(mid)
        if not m:
            continue
        v = m.get("values", {})
        out[mid] = {"title": HEADLINE.get(mid, m.get("title")),
                    "current": v.get("current"), "previous": v.get("previous"),
                    "delta": m.get("delta")}
    return out


def preflight(shop_domain):
    try:
        m = metrics(shop_domain, "2026-06-09", "2026-06-22", ids=["totalRoas"])
        if m.get("totalRoas", {}).get("current") is not None:
            return True, f"TW live (blended ROAS {m['totalRoas']['current']:.2f})"
        return False, "TW responded but no data"
    except Exception as e:  # noqa
        return False, f"TW error: {str(e)[:120]}"


if __name__ == "__main__":
    import sys
    shop = sys.argv[1] if len(sys.argv) > 1 else "example-brand.myshopify.com"
    ok, msg = preflight(shop)
    print(("OK: " if ok else "BLOCKED: ") + msg)
