from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import retail_detail_catalog as rdc

WATSONS_SEED = """
<html><body>
<a href="/en/in-2-it-in2it-kombucha-miracle-water-essence-150ml./p/BP_298456">View product</a>
<a href="/en/c/skincare">Skincare category</a>
<script>window.routes=["\\/en\\/another-product\\/p\\/BP_777777"]</script>
</body></html>
"""
WATSONS_DETAIL = """
<html><head>
<link rel="canonical" href="https://www.watsons.co.th/en/in-2-it-in2it-kombucha-miracle-water-essence-150ml./p/BP_298456">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"In2it Kombucha Miracle Water Essence 150ml.",
 "sku":"298456","brand":{"@type":"Brand","name":"In 2 It"},"image":"https://example/image.jpg",
 "offers":{"@type":"Offer","price":"129.00","highPrice":"259.00","priceCurrency":"THB","availability":"https://schema.org/InStock"}}
</script></head><body><h1>In2it Kombucha Miracle Water Essence 150ml.</h1></body></html>
"""

JIB_SEED = """
<html><body>
<a href="/web/product/readProduct/71671/2114/COMPUTER-SET-JIB-MARU-2411052">COMPUTER SET JIB MARU</a>
<img src="/img_master/product/medium/20260828104049_0000086617_447_1.jpg">
<a href="/web/category/1">Category</a>
</body></html>
"""
JIB_DETAIL = """
<html><head><link rel="canonical" href="https://www.jib.co.th/web/product/readProduct/71671/2114/COMPUTER-SET-JIB-MARU-2411052"></head>
<body><h1>COMPUTER SET JIB MARU-2411052</h1><div>(#COMSET2411052)</div><div>ราคา บาท 28,190</div></body></html>
"""


def fake_get(url, timeout=15, headers=None):
    if "watsons.co.th" in url:
        html = WATSONS_DETAIL if "/p/BP_" in url else WATSONS_SEED
    elif "jib.co.th" in url:
        html = JIB_DETAIL if "/web/product/readProduct/" in url else JIB_SEED
    else:
        return {"ok": False, "status": 404, "error": "not found"}
    return {"ok": True, "status": 200, "final_url": url, "text": html, "bytes": len(html), "content_type": "text/html"}


def fake_browser(url, timeout=35):
    html = WATSONS_SEED if "watsons.co.th" in url else JIB_SEED
    return {"ok": True, "available": True, "html": html, "urls": [], "rows": [], "stderr": ""}


original_get, original_browser = rdc.get, rdc.browser_render
rdc.get, rdc.browser_render = fake_get, fake_browser
try:
    watsons = rdc.generic_retail_detail_catalog("https://www.watsons.co.th/en/", max_pages=4)
    jib = rdc.generic_retail_detail_catalog("https://www.jib.co.th/web/index.php", max_pages=4)
finally:
    rdc.get, rdc.browser_render = original_get, original_browser

assert watsons["record_count"] >= 1, watsons
w = watsons["sample_records"][0]
assert w["sku"] == "298456"
assert w["price"] == 129.0
assert w["regular_price"] == 259.0
assert w["source_url"].endswith("/p/BP_298456")
assert watsons["potential"]["identity_completeness_pct"] == 100.0

assert jib["record_count"] == 1, jib
j = jib["sample_records"][0]
assert j["sku"] == "COMSET2411052"
# The numeric route segments identify the official canonical detail route, but are
# not promoted to a business model field without explicit page evidence.
assert j["model"] == ""
assert j["price"] == 28190.0
assert "/web/product/readProduct/71671/2114/" in j["source_url"]

assert rdc.product_url_score("https://www.jib.co.th/img_master/product/medium/a.jpg", seed_url="https://www.jib.co.th/") < 0
assert rdc.product_url_score("https://www.watsons.co.th/en/c/skincare", seed_url="https://www.watsons.co.th/en/") < 25
assert rdc.product_url_score("https://www.watsons.co.th/en/x/p/BP_123456", seed_url="https://www.watsons.co.th/en/") >= 80

print("Canonical retail product-detail catalog: PASS")
