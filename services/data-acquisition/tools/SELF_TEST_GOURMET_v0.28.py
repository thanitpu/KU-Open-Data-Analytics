from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'acquisition'))
import supermarket_techniques as st
import technique_strategy as ts
import deep_audit as da

html='''<html><body>
<a class="product-card" href="/th/coke-zero-8851959108741">
<img alt="โค้ก ไม่มีน้ำตาล 325 มล." src="/_next/image?url=https%3A%2F%2Fmedia-stark.gourmetmarketthailand.com%2Fproducts%2Fthumbnail%2F8851959108741-1-1757558463.495.webp&w=640&q=75">
<span>฿18</span><del>฿20</del></a>
<a class="product-card" href="/th/fanta-orange-8851959108178">
<img alt="แฟนต้า น้ำส้ม 325 มล." src="https://media-stark.gourmetmarketthailand.com/products/thumbnail/8851959108178-1.webp">
<span>฿17</span></a>
<a href="/promotion/fresh-deal"><img alt="Fresh Deal ลดสูงสุด 30%" src="/banner/promotion-fresh.webp"></a>
<img alt="ผักและผลไม้" src="/categories/Fruit.webp">
</body></html>'''
rows,stats=st._gourmet_product_rows_from_rendered(html)
assert len(rows)==2,(rows,stats)
assert rows[0]['sku']=='8851959108741' and rows[0]['price']==18
assert rows[0]['regular_price']==20
assert rows[0]['provenance']=='gourmet-rendered-product-card'
assert da._semantically_plausible_product(rows[0])

obj={'data':{'products':[{'name':'โค้ก ไม่มีน้ำตาล 325 มล.','sku':'8851959108741','sellingPrice':18,'regularPrice':20,'slug':'th/coke-zero-8851959108741'}]}}
g=st._gourmet_graphql_rows(obj)
assert len(g)==1 and g[0]['price']==18 and g[0]['sku']=='8851959108741'
assert g[0]['provenance']=='gourmet-graphql-product'
assert da._semantically_plausible_product(g[0])

js='const q=`query SearchProducts($limit: Int!, $page: Int!){ products(limit:$limit,page:$page){ name sku sellingPrice } }`;'
docs=st._graphql_docs_from_js(js)
assert docs and 'SearchProducts' in docs[0],docs
vars,unknown=st._gourmet_query_variables(docs[0])
assert vars.get('limit')==20 and vars.get('page')==1 and not unknown,(vars,unknown)

results=[
 {'technique':'generic_browser_rendered','label':'Browser-rendered DOM','status':'completed','record_count':98,
  'record_types':[{'type':'PromotionListingItemCandidate','count':97}], 'sample_records':[{'record_type':'PromotionListingItemCandidate','promotion_title':'ผักและผลไม้','source_url':'https://gourmetmarketthailand.com/'}],
  'potential':{'discovered_urls':175,'confidence':'medium'},'elapsed_seconds':4,'pages_checked':1},
 {'technique':'gourmet_rendered_catalog','label':'Gourmet Market Rendered Product Cards','status':'completed','record_count':2,
  'record_types':[{'type':'ProductCandidate','count':2}],'sample_records':rows,
  'potential':{'product_records':2,'price_completeness_pct':100,'sku_completeness_pct':100,'confidence':'high'},'elapsed_seconds':4,'pages_checked':1},
 {'technique':'gourmet_promotion_surface','label':'Gourmet Market Official Promotion Surface','status':'completed','record_count':1,
  'record_types':[{'type':'PromotionCandidate','count':1}], 'sample_records':[{'record_type':'PromotionCandidate','promotion_title':'Fresh Deal ลดสูงสุด 30%','source_url':'https://gourmetmarketthailand.com/promotion/fresh-deal','provenance':'gourmet-official-promotion'}],
  'potential':{'promotion_records':1,'confidence':'high'},'elapsed_seconds':4,'pages_checked':1},
 {'technique':'gourmet_catalog_network','label':'Gourmet GraphQL / Network Catalog Discovery','status':'completed','record_count':1,
  'record_types':[{'type':'EndpointCandidate','count':1}],'sample_records':[{'record_type':'EndpointCandidate','title':st.GOURMET_GRAPHQL,'source_url':st.GOURMET_GRAPHQL}],
  'potential':{'api_candidates':1,'product_identity_candidates':55,'discovered_urls':161,'confidence':'high'},'elapsed_seconds':4,'pages_checked':1}
]
recs,tracks=ts.recommend_supermarket_tracks(results,'gourmet')
assert tracks['product_price']['technique']=='gourmet_rendered_catalog',tracks
assert tracks['promotion']['technique']=='gourmet_promotion_surface',tracks
assert tracks['discovery']['technique']=='gourmet_catalog_network',tracks
assert 'generic_browser_rendered' not in [r['technique'] for r in recs],recs
assert ts.is_gourmet('https://gourmetmarketthailand.com/')
for k in ('gourmet_graphql_catalog','gourmet_rendered_catalog','gourmet_promotion_surface','gourmet_catalog_network'):
    assert k in ts.applicable_techniques('https://gourmetmarketthailand.com/')
assert ts.TECHNIQUE_ENGINE_VERSION=='0.24'
print('[PASS] v0.28 Gourmet Market source-specific acquisition patterns')
