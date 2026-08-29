from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / 'acquisition', ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gourmet_detail_technique import gourmet_detail_record, gourmet_detail_links

html = '''<!doctype html><html><head>
<meta property="og:title" content="Doi Chang Espresso Supreme 250G | Gourmet Market">
<script type="application/ld+json">{
  "@context":"https://schema.org","@type":"Product","name":"Doi Chang Espresso Supreme 250G",
  "brand":{"@type":"Brand","name":"DOI CHAANG"},"gtin13":"8856709000498",
  "category":"Beverages > Coffee","offers":{"@type":"Offer","price":"290.00","priceCurrency":"THB"}
}</script></head><body>
<h1>Doi Chang Espresso Supreme 250G</h1><div>฿290.00 / Each</div>
<a href="/en/doi_chang_roast__ground_premium_classic_250g_8856709000467">Similar product</a>
</body></html>'''

url = 'https://gourmetmarketthailand.com/en/doi_chang_roastground_espresso_supreme_250g_8856709000498'
r = gourmet_detail_record(html, url)
assert r is not None
assert r['record_type'] == 'ProductCandidate'
assert r['sku'] == '8856709000498'
assert r['price'] == 290.0
assert r['brand'] == 'DOI CHAANG'
assert r['provenance'] == 'gourmet-product-detail'
assert r['source_url'].startswith('https://gourmetmarketthailand.com/th/')
links = gourmet_detail_links(html, url)
assert len(links) == 1 and links[0].endswith('8856709000467')

visible = '''<html><head><meta property="og:title" content="Gourmet Fresh Holy Basil 100G | Gourmet Market"></head>
<body><h1>Gourmet Fresh Holy Basil 100G</h1><div>Brand: Gourmet Fresh</div><div>฿35.00 / Each</div></body></html>'''
r2 = gourmet_detail_record(visible, 'https://gourmetmarketthailand.com/th/gourmet_fresh_holy_basil_100g_63423')
assert r2 is not None and r2['sku'] == '63423' and r2['price'] == 35.0
assert r2['parser_mode'] == 'visible-detail'

# A numeric page without explicit current price must not become a product observation.
no_price = '<html><head><meta property="og:title" content="Example Product | Gourmet Market"></head><body><h1>Example Product</h1><div>250G</div></body></html>'
assert gourmet_detail_record(no_price, 'https://gourmetmarketthailand.com/en/example_product_8850000000000') is None

print('Gourmet product-detail technique: PASS')
