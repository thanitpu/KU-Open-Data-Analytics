from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/'acquisition',ROOT/'repository',ROOT):
    if str(p) not in sys.path:sys.path.insert(0,str(p))

import supermarket_techniques as sm
import technique_strategy as ts


def check(condition,label,detail=None):
    if not condition:raise AssertionError(f'{label}: {detail}')
    print(f'[PASS] {label}')

# Big C category-card structure based on the public official category surface.
bigc_html='''<html><body>
<div class="product-card"><a href="/product/we-are-fresh-fresh-egg-mixed-size-pack-30.26909">วี อาร์ เฟร็ช ไข่ไก่คละขนาด แพ็ค 30</a><span class="price">109.00</span><span class="regular-price">฿125.00</span></div>
<div class="product-card"><a href="/product/dna-soy-milk.50">ดีน่า นมถั่วเหลือง 180 มล. X 4 ชิ้น</a><span data-testid="price">36.00</span><del class="regular-price">฿38.00</del></div>
</body></html>'''
br=sm.bigc_listing_rows(bigc_html,'https://www.bigc.co.th/category/eggs-milk-dairy-products')
check(len(br)==2,'Big C card count',br)
check(br[0]['sku']=='26909','Big C SKU from canonical product URL',br[0])
check(br[0]['price']==109 and br[0]['regular_price']==125,'Big C current/regular price pairing',br[0])
check(br[1]['price']==36 and br[1]['regular_price']==38,'Big C second card price pairing',br[1])

# Makro PRO listing + detail structures based on public official product pages.
makro_html='''<html><body>
<div class="card"><a href="/en/p/woicih7-6761199108291?info=xyz">CRYSTAL Drinking Water 600 ml x 12 12 unit(s)CRYSTAL฿49</a></div>
<div class="card"><a href="/th/p/abc-123">สินค้าโปรโมชั่น 1 unit(s)MAKRO฿350 ฿420</a></div>
</body></html>'''
mr=sm.makro_listing_rows(makro_html,'https://www.makro.pro/th/c/search')
check(len(mr)==2,'Makro PRO card count',mr)
check(mr[0]['product_name']=='CRYSTAL Drinking Water 600 ml x 12' and mr[0]['brand']=='CRYSTAL','Makro name/brand split',mr[0])
check(mr[0]['price']==49,'Makro current price',mr[0])
check(mr[1]['price']==350 and mr[1]['regular_price']==420,'Makro promotional current/regular prices',mr[1])
makro_detail='''<html><body><h1>CRYSTAL Drinking Water 600 ml x 12</h1><div>CRYSTAL</div><div>12 unit(s)</div><div>฿ 4.08 per unit</div><div>Code : 219535</div><div>Buy 5 - 11 units</div><div>฿</div><div>47</div><div>฿ 49.00</div><div>SKU</div><div>219535</div></body></html>'''
md=sm.makro_detail_record(makro_detail,'https://www.makro.pro/en/p/woicih7-6761199108291')
check(bool(md) and md['sku']=='219535','Makro detail SKU/code extraction',md)
check(bool(md) and md['brand']=='CRYSTAL','Makro detail brand extraction',md)
check(bool(md) and md['price']==47 and md['regular_price']==49,'Makro detail sale/regular price extraction',md)

# Effective-domain guard: unrelated *.co.th domains must not be treated as same-site.
check(ts.is_bigc('https://www.bigc.co.th/'),'Big C .co.th source detection')
check(ts.is_makro('https://www.makro.co.th/th/index') and ts.is_makro('https://www.makro.pro/th/c/search'),'Makro corporate/PRO source detection')
check(not ts.same_site('https://www.bigc.co.th/x','https://www.makro.co.th/y'),'Thai .co.th same-site isolation')
import deep_audit as da
check(not da._semantically_plausible_product({'product_name':'ซื้อครบ','price':1,'source_url':'https://www.bigc.co.th/','provenance':'text-pattern'}),'Big C coupon-text semantic rejection')
check(da._semantically_plausible_product({'product_name':'สินค้า A','price':49,'sku':'21','source_url':'https://www.bigc.co.th/product/a.21','provenance':'bigc-sitemap-product-detail'}),'Big C product-detail semantic identity')

bigc_catalog={'technique':'bigc_product_catalog','label':'Big C Sitemap Product Detail Catalog','status':'completed','record_count':30,
 'record_types':[{'type':'ProductCandidate','count':30}],'sample_records':br*15,'elapsed_seconds':3,'pages_checked':1,
 'potential':{'confidence':'high','price_completeness_pct':100,'reported_pages':42,'estimated_extractable_records_high':1260}}
bigc_promo={'technique':'bigc_promotion_surface','label':'Big C Official Campaign Surface','status':'completed','record_count':3,
 'record_types':[{'type':'PromotionCandidate','count':3}],'sample_records':[{'record_type':'PromotionCandidate','promotion_title':'Flash Sale','source_url':'u','provenance':'bigc-official-campaign'}]*3,
 'elapsed_seconds':2,'pages_checked':3,'potential':{'confidence':'high'}}
bigc_noisy={'technique':'basic_crawler','label':'Basic HTML Crawler','status':'completed','record_count':8,
 'record_types':[{'type':'ProductCandidate','count':1},{'type':'PromotionCandidate','count':7}],
 'sample_records':[{'record_type':'ProductCandidate','product_name':'ซื้อครบ','price':1,'source_url':'u','provenance':'text-pattern'}],
 'elapsed_seconds':5,'pages_checked':5,'potential':{}}
bigc_sitemap={'technique':'generic_sitemap','label':'Robots / Sitemap Discovery','status':'completed','record_count':12,
 'record_types':[{'type':'URLCandidate','count':12}],'sample_records':[{'record_type':'URLCandidate','source_url':'u'}],
 'elapsed_seconds':3,'pages_checked':5,'potential':{'confidence':'high','discovered_urls':61946}}
_,bt=ts.recommend_supermarket_tracks([bigc_noisy,bigc_catalog,bigc_promo,bigc_sitemap],'bigc')
check(bt['product_price']['technique']=='bigc_product_catalog','Big C Product & Price track ranking',bt)
check(bt['promotion']['technique']=='bigc_promotion_surface','Big C Promotion track ranking',bt)

makro_catalog={'technique':'makro_pro_catalog','label':'Makro PRO Product Catalog Surface','status':'completed','record_count':40,
 'record_types':[{'type':'ProductCandidate','count':40}],'sample_records':mr*20,'elapsed_seconds':3,'pages_checked':2,
 'potential':{'confidence':'high','price_completeness_pct':100,'reported_total':69784,'estimated_extractable_records_high':69784}}
makro_promo={'technique':'makro_promotion_catalogue','label':'Makro Promotions Catalogue Surface','status':'completed','record_count':2,
 'record_types':[{'type':'PromotionCandidate','count':2}],'sample_records':[{'record_type':'PromotionCandidate','promotion_title':'Makro Catalogue','source_url':'u','provenance':'makro-official-catalogue'}]*2,
 'elapsed_seconds':1,'pages_checked':2,'potential':{'confidence':'high','reported_products':600}}
_,mt=ts.recommend_supermarket_tracks([makro_catalog,makro_promo],'makro')
check(mt['product_price']['technique']=='makro_pro_catalog','Makro Product & Price track ranking',mt)
check(mt['promotion']['technique']=='makro_promotion_catalogue','Makro Promotion track ranking',mt)
check(mt['discovery']['technique']=='makro_pro_catalog','Makro reported-total coverage track',mt)

print(json.dumps({'ok':True,'bigc_tracks':{k:v['technique'] for k,v in bt.items()},'makro_tracks':{k:v['technique'] for k,v in mt.items()}},ensure_ascii=False))

# v0.25: current public Big C detail representation (compact labels + selling/original price).
bigc_detail_live_shape='''<html><head><meta property="og:title" content="รอกโก ข้าวโพดอบกรอบสอดไส้โกโก้ 15 ก. แพ็ค 12 - Big C Online"></head><body>
<h1>รอกโก ข้าวโพดอบกรอบสอดไส้โกโก้ 15 ก. แพ็ค 12</h1>
<div>รหัสสินค้า: 21</div><div>฿24/ แพ็ค</div><div>฿49-51%</div>
<div>แบรนด์โรซินันเต้</div><div>หมวดหมู่ขนมอบ ทอดกรอบ</div></body></html>'''
bd=sm.bigc_detail_record(bigc_detail_live_shape,'https://www.bigc.co.th/product/rocco-the-elegant-pastries-20-g-pack-12.21')
check(bool(bd) and bd['price']==24 and bd['regular_price']==49,'Big C live-shape main/current price anchor',bd)
check(bd['brand']=='โรซินันเต้' and bd['category']=='ขนมอบ ทอดกรอบ','Big C compact brand/category labels',bd)

# v0.25: escaped Next/RSC payload must still materialize the focal product.
bigc_rsc='''<html><head><meta property="og:title" content="รอกโก ข้าวโพดอบกรอบสอดไส้โกโก้ 15 ก. แพ็ค 12 - Big C Online"></head><script>self.__next_f.push([1,"รหัสสินค้า: 21\\n฿24/ แพ็ค\\n฿49-51%\\nแบรนด์โรซินันเต้\\nหมวดหมู่ขนมอบ ทอดกรอบ"])</script></html>'''
brsc=sm.bigc_detail_record(bigc_rsc,'https://www.bigc.co.th/product/rocco-the-elegant-pastries-20-g-pack-12.21')
check(bool(brsc) and brsc['price']==24 and brsc['sku']=='21','Big C decoded Next/RSC product detail',brsc)

# v0.25: Makro public search accessible-text representation works even when card DOM hierarchy is unavailable.
makro_text='''<html><body><div>รายการสินค้า</div><div>แสดงสินค้า 1-20 ของ 70075</div>
<script>self.__next_f.push([1,"/p/woicih7-6761199108291\\nคริสตัล น้ําดื่ม 600 มล. x 12 12 unit(s)คริสตัล฿49\\n/p/8e2czhh-7606381641923\\nสะโพกไก่ติดกระดูก 1 กก.1 kgแม็คโคร฿52.50"])</script></body></html>'''
mtxt=sm.makro_text_rows(makro_text,'https://www.makro.pro/th/c/search')
check(len(mtxt)==2,'Makro accessible/SSR text product count',mtxt)
check(mtxt[0]['product_name']=='คริสตัล น้ําดื่ม 600 มล. x 12' and mtxt[0]['brand']=='คริสตัล' and mtxt[0]['price']==49,'Makro accessible text name/brand/price',mtxt[0])
check('/p/woicih7-6761199108291' in mtxt[0]['source_url'],'Makro escaped product path alignment',mtxt[0])
check(da._semantically_plausible_product(mtxt[0]),'Makro accessible text semantic product gate',mtxt[0])

print('[PASS] v0.25 supermarket materialization additions')

# v0.25: Big C multi-template detail parsing from current public shapes.
bigc_template_a="""<html><head><meta property='og:title' content='แลคตาซอย นมถั่วเหลืองยูเอชที แคลเซียมสูง น้ำตาลน้อยกว่า เจ 300 มล. แพ็ค 6 - Big C Online'></head><body>
<div>สินค้าโปรโมชัน</div><div>หมดเขต 06/09/69</div><h1>แลคตาซอย นมถั่วเหลืองยูเอชที แคลเซียมสูง น้ำตาลน้อยกว่า เจ 300 มล. แพ็ค 6</h1>
<div>รหัสสินค้า: 82</div><div>฿56/ แพ็ค</div><div>฿62-9%</div><div>รายละเอียดสินค้า</div><div>แบรนด์แลคตาซอย</div><div>หมวดหมู่<a>นมธัญพืช</a></div>
<h2>สินค้าใกล้เคียง</h2><div>฿35</div><div>฿38</div></body></html>"""
ba=sm.bigc_detail_record(bigc_template_a,'https://www.bigc.co.th/product/lactasoy-uht-soymilk-hi-calcium-300-ml-pack-6.82')
check(bool(ba) and ba['price']==56 and ba['regular_price']==62 and ba['sku']=='82','Big C template A focal current/regular price',ba)
check(ba['brand']=='แลคตาซอย' and ba['category']=='นมธัญพืช','Big C template A split/compact labels',ba)
check(ba['end_date']=='2026-09-06' and 'สินค้าโปรโมชัน' in ba['promotion_mechanic'],'Big C template A promotion validity',ba)

bigc_template_b="""<html><head><meta property='og:title' content='โค้ก น้ำอัดลม สูตรไม่มีน้ำตาล แบบกระป๋อง 325 มล. - Big C Online'></head><body>
<h1>โค้ก น้ำอัดลม สูตรไม่มีน้ำตาล แบบกระป๋อง 325 มล.</h1><div>ID: 89</div><div>฿16/ กระป๋อง</div>
<div>คูปอง</div><div>ลด 45.-</div><div>ซื้อครบ 450.-</div><div>รายละเอียดสินค้า</div><div>แบรนด์</div><a>โค้ก</a><div>หมวดหมู่</div><a>น้ำอัดลม</a>
<h2>สินค้าใกล้เคียง</h2><div>฿36</div><div>฿41</div></body></html>"""
bb=sm.bigc_detail_record(bigc_template_b,'https://www.bigc.co.th/product/coke-no-sugar-soft-drink-325-ml-8851959132074.89')
check(bool(bb) and bb['price']==16 and bb['regular_price'] is None and bb['sku']=='89','Big C template B ID + unit price',bb)
check(bb['brand']=='โค้ก' and bb['category']=='น้ำอัดลม','Big C template B linked labels',bb)

bigc_template_c="""<html><head><meta property='og:title' content='โออิชิ กรีนที ชาเขียว รสต้นตำรับ 500 มล. - Big C Online'></head><body>
<h1>โออิชิ กรีนที ชาเขียว รสต้นตำรับ 500 มล.</h1><div>รหัสสินค้า: 98</div><div>ซื้อ 2 ถูกลง</div><div>฿25/ ขวด</div><div>รายละเอียดสินค้า</div><div>แบรนด์โออิชิ</div><div>หมวดหมู่ชาพร้อมดื่ม</div></body></html>"""
bc=sm.bigc_detail_record(bigc_template_c,'https://www.bigc.co.th/product/oishi-green-tea-original-flavor-500-ml.98')
check(bool(bc) and bc['price']==25 and bc['promo_price']==25,'Big C template C mechanic price',bc)
check('ซื้อ 2 ถูกลง' in bc['promotion_mechanic'],'Big C template C promotion mechanic',bc)

# Flattened/escaped RSC shape with arbitrary separators around SKU and currency.
bigc_flat="""<html><head><meta property='og:title' content='แฟนต้า น้ำอัดลม น้ำเขียว 325 มล. แพ็ค 6 - Big C Online'></head><script>
self.__next_f.push([1,"รหัสสินค้า\\n: \\n85\\nสินค้าโปรโมชัน\\n฿79/ แพ็ค\\n฿90-12%\\nแบรนด์แฟนต้า\\nหมวดหมู่น้ำอัดลม"])</script></html>"""
bf=sm.bigc_detail_record(bigc_flat,'https://www.bigc.co.th/product/fanta-soft-drink-can-green-color-325-ml-pack-6-8851959632185.85')
check(bool(bf) and bf['price']==79 and bf['regular_price']==90 and bf['sku']=='85','Big C flattened RSC focal price',bf)

# v0.25: repeatability must be reported separately by track.
r1=[{'record_type':'ProductCandidate','product_name':'A','price':10,'source_url':'pA'},
    {'record_type':'PromotionCandidate','promotion_title':'Promo','source_url':'x'}]
r2=[{'record_type':'PromotionCandidate','promotion_title':'Promo','source_url':'x'}]
rb=da._repeatability_breakdown(r1,r2)
check(rb['repeatability_pct']>0 and rb['product_repeatability_pct']==0,'Deep Audit product-track repeatability isolation',rb)
check(rb['promotion_repeatability_pct']==100,'Deep Audit promotion-track repeatability isolation',rb)

print('[PASS] v0.25 Big C multi-template + per-track repeatability')

# v0.25: structured Next-state fallback near focal SKU when visible baht text is absent.
bigc_json_state="""<html><head><meta property='og:title' content='แลคตาซอย นมถั่วเหลืองยูเอชที แคลเซียมสูง - Big C Online'></head><script>
self.__next_f.push([1,'{"productId":"82","name":"แลคตาซอย","finalPrice":56,"originalPrice":62,"brand":"แลคตาซอย"}'])</script></html>"""
bj=sm.bigc_detail_record(bigc_json_state,'https://www.bigc.co.th/product/lactasoy-uht-soymilk-hi-calcium-300-ml-pack-6.82')
check(bool(bj) and bj['price']==56 and bj['regular_price']==62,'Big C structured Next-state price fallback',bj)

# v0.25: Makro current DOM can contain multiple anchors for the SAME product card.
makro_current_dom="""<html><body>
<div class='product-card'>
 <a href='/th/p/219535-6761199108291'><img alt='คริสตัล น้ำดื่ม 600 มล. x 12'></a>
 <a href='/th/p/219535-6761199108291'><span>คริสตัล น้ำดื่ม 600 มล. x 12</span></a>
 <span>12 unit(s)</span><span>คริสตัล</span><span>฿49</span>
</div>
<div class='product-card'>
 <a href='/th/p/999999-1234567890123'>ออพติมั่ม อาหารปลา 15 กก.</a>
 <span>1 bag(s)</span><span>ออพติมั่ม</span><span>1,600</span><span>฿1,970</span><span>฿-18%</span>
</div></body></html>"""
mcd=sm.makro_listing_rows(makro_current_dom,'https://www.makro.pro/th/c/search')
check(len(mcd)==2,'Makro duplicate-anchor card materialization',mcd)
check(mcd[0]['sku']=='219535' and mcd[0].get('gtin')=='6761199108291','Makro current route SKU/GTIN identity',mcd[0])
check(mcd[0]['price']==49 and mcd[0]['brand']=='คริสตัล','Makro current DOM normal price',mcd[0])
check(mcd[1]['price']==1600 and mcd[1]['regular_price']==1970 and mcd[1]['brand']=='ออพติมั่ม','Makro discounted card price-before-baht form',mcd[1])

# v0.25: rendered/accessibility text may split title, unit, brand and price across lines.
makro_rendered_text="""รายการสินค้า
แสดงสินค้า 1-20 ของ 70076
เรียงตาม
ความใกล้เคียง
[Input]
คริสตัล น้ําดื่ม 600 มล. x 12
12 unit(s)
คริสตัล
฿49
สิงห์ โซดา 325 มล. x 24
24 unit(s)
สิงห์
฿190
ออพติมั่ม ไฮโปร อาหารปลาคาร์พ เม็ดกลาง 15 กก.
1 bag(s)
ออพติมั่ม
1,600฿1,970฿-18%
"""
mrt=sm._makro_sequence_rows(makro_rendered_text,'https://www.makro.pro/th/c/search',[
 'https://www.makro.pro/th/p/219535-6761199108291',
 'https://www.makro.pro/th/p/219536-6761215066307',
 'https://www.makro.pro/th/p/999999-1234567890123'])
check(len(mrt)==3,'Makro rendered sequence product count',mrt)
check(mrt[0]['product_name'].startswith('คริสตัล') and mrt[0]['price']==49,'Makro rendered sequence first product',mrt[0])
check(mrt[1]['product_name'].startswith('สิงห์ โซดา') and mrt[1]['price']==190,'Makro rendered sequence second product',mrt[1])
check(mrt[2]['price']==1600 and mrt[2]['regular_price']==1970,'Makro rendered sequence discounted product',mrt[2])
check(all(da._semantically_plausible_product(x) for x in mrt),'Makro rendered rows semantic gate',mrt)

# Exact public search text shape observed in Aug 2026.
makro_public_text="""รายการสินค้า
แสดงสินค้า 1-20 ของ 70076
เรียงตาม
ความใกล้เคียง
[Input]
คริสตัล น้ําดื่ม 600 มล. x 12 12 unit(s)คริสตัล฿49
สิงห์ โซดา 325 มล. x 24 24 unit(s)สิงห์฿190
สิงห์ น้ําดื่ม 600 มล. x 12+3 15 unit(s)สิงห์฿57
สิงห์ น้ําดื่ม 1.5 ล. x 6 6 unit(s)สิงห์฿49
เบญจรงค์ ข้าวหอมมะลิ 100% 5 กก.1 unit(s)เบญจรงค์฿209
สะโพกไก่ติดกระดูก 1 กก.1 kgแม็คโคร฿52.50
โอรีโอ คุกกี้แซนวิช 24.6 ก. x 12 12 unit(s)โอรีโอ฿48
"""
mpt=sm._makro_sequence_rows(makro_public_text,'https://www.makro.pro/th/c/search')
check(len(mpt)==7,'Makro current public flattened listing shape',mpt)
check(mpt[5]['price']==52.5 and mpt[5]['brand']=='แม็คโคร','Makro weighed-product unit/price',mpt[5])

print('[PASS] v0.25 Makro PRO resilient materialization')
