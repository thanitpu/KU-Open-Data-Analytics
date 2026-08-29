from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'acquisition'))
from lotus_advanced import visible_promotion_items, extract_urls, scan_json, lotus_catalog_product_rows
from lotus_multitechnique import _dedup

html='''<html><body>
<img alt="สมัครสมาชิกใหม่มายโลตัส"><img alt="Rainy Season แลกคอยน์รับคูปองส่วนลดหน้าฝน">
<img alt="icon"><a href="/promotions/registernew/th">สมัคร</a>
<script type="application/json">{"total":248,"items":[{"type":"Product","name":"LOTUSS TEST MILK","price":42.0,"brand":{"name":"LOTUSS"},"url":"https://www.lotuss.com/th/product/test-123"},{"type":"Promotion","name":"TEST PROMO","description":"ลด 20%","url":"https://my.lotuss.com/promotions/testpromo/th"}]}</script>
</body></html>'''
rows=visible_promotion_items(html,'https://my.lotuss.com/promotions/th')
assert len(rows)==2, rows
urls=extract_urls(html,'https://my.lotuss.com/promotions/th')
assert any('/promotions/registernew/th' in x for x in urls), urls
assert any('/th/product/test-123' in x for x in urls), urls
obj={"total":248,"items":[{"type":"Product","name":"LOTUSS TEST MILK","price":42.0,"brand":{"name":"LOTUSS"}},{"type":"Promotion","name":"TEST PROMO","description":"ลด 20%"}]}
out=[];u=[];m={};scan_json(obj,'https://www.lotuss.com/th',out,u,m)
assert m.get('reported_total')==248,m
assert any(x.get('record_type')=='ProductCandidate' for x in out),out
assert any(x.get('record_type')=='PromotionCandidate' for x in out),out
assert len(_dedup(out))>=2
print('[PASS] Lotus advanced offline fixture')
print(json.dumps({'visible_promotion_items':len(rows),'reported_total':m['reported_total'],'record_types':sorted(set(x['record_type'] for x in out))},ensure_ascii=False))

# Integration fixture: official promotion surface should yield listing-card evidence
# even when client-side code hides ordinary detail hrefs.
import lotus_multitechnique as lm
_listing = """<html><head><title>โปรโมชั่น | My Lotus's</title></head><body>
<img alt='สมัครสมาชิกใหม่มายโลตัส'><img alt='Rainy Season แลกคอยน์รับคูปองส่วนลดหน้าฝน'>
<div>โปรโมชั่นมากมายสำหรับสมาชิกมายโลตัสและลูกค้าทั่วไป พร้อมสิทธิประโยชน์ เงื่อนไข และช่วงเวลารายการ</div>
</body></html>"""
_orig_fetch=lm.fetch
def _fake_fetch(url,timeout=12):
    return {'ok':True,'status':200,'content_type':'text/html','final_url':url,'text':_listing}
lm.fetch=_fake_fetch
try:
    rr=lm.official_surfaces('https://www.lotuss.com/th',3)
    assert rr['record_count']>=2, rr
    assert rr['potential'].get('visible_listing_items')==2, rr['potential']
    print('[PASS] Promotion surface visible-card fallback')
finally:
    lm.fetch=_orig_fetch
assert len(lm.TECHNIQUES)>=12
print('[PASS] Advanced technique registry:',len(lm.TECHNIQUES))


# Exact public Lotus O2O product API schema fixture observed from /product/v4/products.
api_fixture={
 "code":200,"message":"success","data":{"products":[
  {"id":111257,"sku":"75741094","name":"ดิงดิง เฟรช ปลาช่อนซุปผักดองแช่แข็ง รสพริกเสฉวน 500 กรัม",
   "urlKey":"75741094","stockStatus":"IN_STOCK","stockOnHand":9999,
   "regularPricePerUOW":159,"finalPricePerUOW":149,"loyaltyMemberPricePerUOW":0,
   "thumbnail":{"url":"https://o2o-static.lotuss.com/products/107486/75741094.jpg"},
   "priceRange":{"minimumPrice":{"regularPrice":{"value":159},"finalPrice":{"value":149},
                                  "discount":{"amountOff":10,"percentOff":6.28}}},"promotions":[]},
  {"id":94698,"sku":"51273938","name":"มาสเตอร์เชฟ สันนอกหมูสไลซ์ชาบู 1 กก.",
   "urlKey":"51273938","stockStatus":"IN_STOCK",
   "regularPricePerUOW":235,"finalPricePerUOW":235,"loyaltyMemberPricePerUOW":199,
   "thumbnail":{"url":"https://o2o-static.lotuss.com/products/107486/51273938.jpg"},"promotions":[]}
 ],"breadcrumb":[{"id":107486,"name":"","urlKey":"meat"}]}}
api_url="https://api-o2o.lotuss.com/lotuss-mobile-bff/product/v4/products?page=1&limit=15&category_path=meat&seller_id=3"
api_rows=lotus_catalog_product_rows(api_fixture,api_url)
assert len(api_rows)==2,api_rows
assert api_rows[0]['price']==149 and api_rows[0]['regular_price']==159 and api_rows[0]['promo_price']==149,api_rows[0]
assert api_rows[1]['member_price']==199,api_rows[1]
assert api_rows[0]['source_url']=='https://www.lotuss.com/th/product/75741094',api_rows[0]
print('[PASS] Lotus O2O catalog schema mapping:',len(api_rows),'products')
