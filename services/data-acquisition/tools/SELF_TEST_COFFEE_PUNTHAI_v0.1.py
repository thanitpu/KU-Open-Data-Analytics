from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / 'acquisition', ROOT):
    if str(p) not in sys.path: sys.path.insert(0, str(p))

from coffee_techniques import punthai_menu_record, punthai_detail_links, audit_punthai_runs


def html(name, price, size, slug2=None):
    link = f'<a href="/en/product/coffee/{slug2}">Related</a>' if slug2 else ''
    return f'''<html><head><meta property="og:title" content="{name} | Punthai Coffee"></head><body>
    <h1>{name}</h1><div>Coffee</div><div>Price {price} Baht</div><div>Size {size} Oz.</div>{link}</body></html>'''

urls = [
    ('hot-espresso','Hot Espresso',40,6), ('espresso','Iced Espresso',60,22),
    ('iced-americano','Iced Americano',60,22), ('hot-americano','Hot Americano',50,6),
    ('hot-latte','Hot Latte',55,6), ('hot-thairicano','Hot Thairicano',60,10),
]
records=[]
for slug,name,price,size in urls:
    r=punthai_menu_record(html(name,price,size), f'https://www.punthaicoffee.com/en/product/coffee/{slug}', observed_at='2026-08-29T00:00:00+00:00')
    assert r and r['menu_item_name']==name and r['price']==float(price) and r['currency']=='THB'
    assert r['provenance']=='punthai-official-menu-detail' and r['size']==f'{size} Oz.'
    records.append(r)
links=punthai_detail_links(html('Hot Espresso',40,6,'hot-latte'),'https://www.punthaicoffee.com/en/product/coffee/hot-espresso')
assert links==['https://www.punthaicoffee.com/en/product/coffee/hot-latte']
a=audit_punthai_runs({'ok':True,'records':records},{'ok':True,'records':records})
assert a['audit_passed'] is True and a['repeatability']['menu_repeatability_pct']==100.0
assert punthai_menu_record('<h1>250 Gram Coffee</h1><div>22 Oz.</div>','https://www.punthaicoffee.com/en/product/coffee/foo') is None
print('Coffee PunThai official menu technique: PASS')
