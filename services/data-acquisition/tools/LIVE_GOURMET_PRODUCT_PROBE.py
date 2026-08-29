from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / 'acquisition'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from source_discovery import search_web
from lotus_advanced import get, browser_render

KNOWN = [
    'https://gourmetmarketthailand.com/en/allowrie_unsalted_butter_10g_pack_8_8850332162158',
    'https://gourmetmarketthailand.com/th/gourmet_fresh_holy_basil_100g_63423',
    'https://gourmetmarketthailand.com/en/doi_chang_roastground_espresso_supreme_250g_8856709000498',
]


def is_productish(url: str) -> bool:
    if 'gourmetmarketthailand.com' not in (urlparse(url).netloc or '').lower():
        return False
    path = urlparse(url).path.rstrip('/').split('/')[-1]
    return bool(re.search(r'_(?:\d{5,14})$', path))


def main():
    rows=[]
    discovered=[]
    for q in [
        'site:gourmetmarketthailand.com 885 gourmet',
        'site:gourmetmarketthailand.com/en 885 product',
        'site:gourmetmarketthailand.com/th 885 สินค้า',
    ]:
        try:
            for r in search_web(q, limit=8, timeout=15):
                u=r.get('url') or ''
                if is_productish(u) and u not in discovered:
                    discovered.append(u)
        except Exception as e:
            rows.append({'query':q,'stage':'search','error':f'{type(e).__name__}: {e}'})
    targets=[]
    for u in KNOWN+discovered:
        if u not in targets: targets.append(u)
    for u in targets[:8]:
        direct=get(u,timeout=15)
        rendered=browser_render(u,timeout=30)
        html=rendered.get('html') or ''
        rows.append({
            'url':u,
            'direct_ok':bool(direct.get('ok')),
            'direct_status':direct.get('status'),
            'direct_bytes':direct.get('bytes',0),
            'direct_error':direct.get('error'),
            'browser_available':rendered.get('available'),
            'browser_ok':rendered.get('ok'),
            'browser_dom_bytes':len(html),
            'browser_has_baht':('฿' in html or '&#3647;' in html),
            'browser_has_gtin':bool(re.search(r'\b\d{12,14}\b',html)),
            'browser_title_match':any(x.lower() in html.lower() for x in ['Allowrie','Doi Chang','ใบกระเพรา']),
            'browser_error':rendered.get('error') or rendered.get('stderr'),
        })
    out={'discovered_product_urls':discovered,'targets_tested':len([x for x in rows if x.get('url')]),'results':rows}
    p=ROOT.parent.parent/'docs'/'validation'/'gourmet-product-probe.json'
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__':main()
