from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT,ROOT/'acquisition'):
    if str(p) not in sys.path: sys.path.insert(0,str(p))

from lotus_advanced import get,browser_render
from supermarket_techniques import _gourmet_post_json

TARGET='https://gourmetmarketthailand.com/en/allowrie_unsalted_butter_10g_pack_8_8850332162158'
GRAPHQL='https://api-stark.gourmetmarketthailand.com/graphql'

def main():
    direct=get(TARGET,timeout=15)
    home=get('https://gourmetmarketthailand.com/',timeout=15)
    gql=_gourmet_post_json(GRAPHQL,{'query':'query KU2DProbe { __typename }'},timeout=15)
    rendered=browser_render(TARGET,timeout=35)
    html=rendered.get('html') or ''
    result={
      'platform':platform.platform(),
      'python':sys.version,
      'home':{k:home.get(k) for k in ('ok','status','bytes','error')},
      'product':{k:direct.get(k) for k in ('ok','status','bytes','error')},
      'graphql':{k:gql.get(k) for k in ('ok','status','bytes','error')},
      'browser':{'available':rendered.get('available'),'ok':rendered.get('ok'),'browser':rendered.get('browser'),'dom_bytes':len(html),'has_product':('Allowrie' in html),'has_price':('฿90' in html or '90.00' in html)},
    }
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    out=Path('gourmet-env-probe.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

if __name__=='__main__':main()
