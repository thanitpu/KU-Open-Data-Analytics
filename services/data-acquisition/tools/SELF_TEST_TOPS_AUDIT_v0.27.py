from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'acquisition'),str(ROOT/'repository'),str(ROOT)]
import deep_audit as da
import supermarket_techniques as st
import technique_strategy as ts

# 1) Track-scoped audit facts: generic crawler product noise assigned only to Promotion
# must never dilute Product & Price semantic quality.
prod=[{'record_type':'ProductCandidate','product_name':f'Product {i}','price':10+i,'sku':f'88500000000{i:02d}',
       'source_url':f'https://www.tops.co.th/th/product-{i}-88500000000{i:02d}','provenance':'tops-sitemap-product-detail'} for i in range(5)]
promo=[{'record_type':'PromotionCandidate','promotion_title':'Fresh deal','offer':'ลด ฿100 เมื่อครบ ฿600',
        'source_url':'https://www.tops.co.th/th/campaign/fresh','provenance':'tops-official-campaign'}]
garbage=[{'record_type':'ProductCandidate','product_name':'สมัคร Tops Prime วันนี้เพียง','price':1,
          'source_url':'https://www.tops.co.th/th','provenance':'text-pattern'}]
run={'records':prod+promo+garbage,'technique_tracks':{
       'product_price':{'technique':'tops_product_catalog'},'promotion':{'technique':'tops_promotion_surface'}},
     'technique_results':[
       {'technique':'tops_product_catalog','sample_records':prod},
       {'technique':'tops_promotion_surface','sample_records':promo},
       {'technique':'basic_crawler','sample_records':garbage}]}
scoped=da._audit_business_records(run)
assert len([x for x in scoped if x['record_type']=='ProductCandidate'])==5,scoped
assert all(x.get('provenance')!='text-pattern' for x in scoped),scoped
assert da._pct(sum(da._semantically_plausible_product(x) for x in scoped if x['record_type']=='ProductCandidate'),5)==100.0
print('[PASS] Tops audit quality is scoped to assigned tracks')

# 2) A smaller stable repeat sample is a reproducibility test, not a Jaccard-size penalty.
r1=prod*1
r2=prod[:3]
rep=da._repeatability_breakdown(r1,r2)
assert rep['product_repeatability_pct']==100.0,rep
assert rep['product']['set_similarity_pct']==60.0,rep
print('[PASS] Stable bounded repeat sample scores 100% reproducibility')

# 3) Canonicalize escaped sitemap paths.
u=st._canonical_tops_product_url('https://www.tops.co.th/th/%20-laverland-crunch-wasabi-seaweed-45g-pack-9-8802241131671')
assert '%20' not in u and '/th/laverland-' in u,u
print('[PASS] Tops escaped sitemap path cleanup')

# 4) Stable operational sample ignores monitoring cursor offset.
orig_universe,orig_get=st._tops_product_universe,st.get
try:
    urls=[f'https://www.tops.co.th/th/item-{i}-88500000000{i:02d}' for i in range(20)]
    st._tops_product_universe=lambda seed,max_sitemaps=16:(urls,['sitemap'],[])
    def fake_get(url,timeout=12,headers=None):
        sku=st._tops_sku(url)
        html=f'<h1>Item {sku}</h1><div>SKU {sku}</div><div>{10+urls.index(url)} / ชิ้น</div><div>รายละเอียดสินค้า</div>'
        return {'ok':True,'text':html,'final_url':url,'bytes':len(html)}
    st.get=fake_get
    x=st.tops_product_catalog('https://www.tops.co.th/th',max_pages=5,source_id='SRC-X',progressive=True,stable_sample=True)
    assert x['urls_checked'][0]==urls[0],x['urls_checked'][:2]
    assert len(x['rows'])==5,x
finally:
    st._tops_product_universe,st.get=orig_universe,orig_get
print('[PASS] Tops Deep Audit stable sample starts from the same catalog prefix')

# 5) Promotion extractor survives homepage 403 by using official campaign surface fallback.
orig_get=st.get
PROMO='''<html><body><h1>โปรของสด ลดท้ายเดือน</h1>\nโปรของสด ลดท้ายเดือน\nลด ฿120 เมื่อช็อปอาหารสด ครบ ฿600/ใบเสร็จ\nเฉพาะวันสั่งซื้อ : 25 ส.ค. 2569 - 31 ส.ค. 2569</body></html>'''
try:
    def fake_get2(url,timeout=12,headers=None):
        if url.endswith('sitemap.th-campaigns.xml'):
            return {'ok':True,'text':'<urlset><url><loc>https://www.tops.co.th/th/campaign/fresh-test</loc></url></urlset>','final_url':url,'bytes':100}
        if url.endswith('sitemap.en-campaigns.xml'):
            return {'ok':False,'status':404,'error':'fixture 404'}
        if url==st.TOPS_HOME:
            return {'ok':False,'status':403,'error':'fixture 403'}
        if '/campaign/' in url:
            return {'ok':True,'text':PROMO,'final_url':url,'bytes':len(PROMO)}
        return {'ok':False,'status':404,'error':'fixture miss'}
    st.get=fake_get2
    p=st.tops_promotion_surface(max_pages=3)
    assert p['rows'],p
    assert any(r.get('end_date')=='2026-08-31' for r in p['rows']),p
finally:
    st.get=orig_get
print('[PASS] Tops official promotion surface campaign-sitemap fallback')

# 6) Source-specific official promotion wins over generic crawler.
results=[
 {'technique':'basic_crawler','label':'Basic HTML Crawler','status':'completed','record_count':50,
  'record_types':[{'type':'PromotionCandidate','count':20}],
  'sample_records':[{'record_type':'PromotionCandidate','promotion_title':'ช็อป','source_url':'https://www.tops.co.th/th','provenance':'optimized-retail-promotion'}]},
 {'technique':'tops_product_catalog','label':'Tops Sitemap Product Detail Catalog','status':'completed','record_count':5,
  'record_types':[{'type':'ProductCandidate','count':5}], 'sample_records':prod,'potential':{'confidence':'high'}},
 {'technique':'tops_promotion_surface','label':'Tops Official Campaign Surface','status':'completed','record_count':1,
  'record_types':[{'type':'PromotionCandidate','count':1}], 'sample_records':promo,'potential':{'confidence':'high'}},
 {'technique':'generic_sitemap','label':'Robots / Sitemap Discovery','status':'completed','record_count':12,
  'record_types':[{'type':'URLCandidate','count':12}], 'potential':{'discovered_urls':187118,'confidence':'high'}}]
_,tracks=ts.recommend_supermarket_tracks(results,'tops')
assert tracks['promotion']['technique']=='tops_promotion_surface',tracks
print('[PASS] Tops official promotion technique outranks Basic Crawler')

assert ts.TECHNIQUE_ENGINE_VERSION=='0.24'
print('[PASS] v0.27 keeps global Technique Engine contract at 0.24')
