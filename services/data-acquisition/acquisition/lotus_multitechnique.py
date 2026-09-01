from __future__ import annotations
import json,re,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlparse,urljoin
from actual_acquisition import discover as basic_discover, fetch, parse_page
from source_adapters import adapter_for, normalize_acquisition
from optimized_adapters import generic_retail_records
from source_discovery import search_web
from lotus_advanced import robots_sitemaps, script_bundle_mining, browser_render, browser_netlog, probe_json_endpoints, multi_search, visible_promotion_items, extract_urls, uniq, json_objects, scan_json

TECHNIQUES = [
    {"key":"basic_crawler","label":"Basic HTML Crawler","description":"Direct HTTP fetch + same-domain link crawl + existing retail text rules."},
    {"key":"structured_data","label":"Structured / Embedded Data","description":"Inspect JSON-LD and embedded application JSON for product/promotion objects."},
    {"key":"official_surfaces","label":"My Lotus’s Promotion Surface","description":"Enumerate and sample official promotion pages from my.lotuss.com."},
    {"key":"product_surface","label":"Lotus Product / Price Surface","description":"Discover official /th/product/ detail pages and test product, brand, category and price extraction."},
    {"key":"category_product_catalog","label":"Lotus Category Product & Price Catalog","description":"Render Lotus category pages, enumerate visible product detail URLs, then materialize product names and prices from official product pages."},
    {"key":"lotus_catalog_api","label":"Lotus Catalog API","description":"Discover Lotus’s public catalog/search API from the exact category/browser network, then read product and price JSON with bounded read-only requests."},
    {"key":"corporate_campaigns","label":"Lotus Corporate Campaign Surface","description":"Discover campaigns and promotion detail pages from corporate.lotuss.com."},
    {"key":"search_assisted","label":"Search-assisted Coverage Discovery","description":"Use a public web index to estimate discoverable official Lotus’s product/promotion/campaign URLs; extraction remains official-site only."},
    {"key":"sitemap_discovery","label":"Robots / Sitemap Discovery","description":"Inspect official robots.txt and sitemap indexes for product, promotion and campaign URLs."},
    {"key":"app_bundle_mining","label":"JavaScript / App Bundle Mining","description":"Inspect application JSON, JavaScript bundles, routes and API-like references delivered to the browser."},
    {"key":"browser_rendered","label":"Browser-rendered DOM","description":"Use local Chrome/Edge headless rendering to expose JavaScript-created DOM content and links."},
    {"key":"browser_network","label":"Browser Network / API Discovery","description":"Capture Chrome/Edge network requests to discover XHR/fetch/catalog/content endpoints."},
    {"key":"api_json_probe","label":"Discovered JSON/API Probe","description":"Bounded read-only probes of official JSON endpoints found from bundles/network traffic."},
    {"key":"multi_index","label":"Multi-index Official URL Discovery","description":"Try several public search indexes and keep only official Lotus’s URLs."},
]

def _host(url):
    try:return (urlparse(url).netloc or '').lower().removeprefix('www.')
    except:return ''

def _is_lotus(url):
    h=_host(url)
    return h=='lotuss.com' or h.endswith('.lotuss.com')

def _dedup(rows):
    out=[];seen=set()
    for r in rows or []:
        k=(r.get('record_type'),r.get('product_name') or r.get('promotion_title') or r.get('title'),r.get('price'),r.get('source_url'))
        if k not in seen:seen.add(k);out.append(r)
    return out

def _types(rows):
    d={}
    for r in rows or []:
        t=r.get('record_type') or 'Unknown';d[t]=d.get(t,0)+1
    return [{"type":k,"count":v} for k,v in sorted(d.items(),key=lambda kv:(-kv[1],kv[0]))]

def _result(key,label,status,records=None,pages=0,diagnostics=None,elapsed=0,urls=None,note='',potential=None):
    records=_dedup(records or [])
    return {"technique":key,"label":label,"status":status,"record_count":len(records),"record_types":_types(records),
            "pages_checked":pages,"sample_records":records[:8],"diagnostics":diagnostics or [],
            "elapsed_seconds":round(elapsed,2),"urls_checked":urls or [],"note":note,"potential":potential or {}}

def basic_crawler(url,max_pages=3):
    t=time.time();label='Basic HTML Crawler'
    try:
        x=basic_discover(url,max(1,min(max_pages,5)))
        return _result('basic_crawler',label,'completed',x.get('records'),len(x.get('pages') or []),x.get('diagnostics'),time.time()-t,
                       [p.get('url') for p in x.get('pages') or []],f"Adapter: {x.get('adapter','generic')}")
    except Exception as e:
        return _result('basic_crawler',label,'failed',diagnostics=[{"error":f"{type(e).__name__}: {e}"}],elapsed=time.time()-t)

def _walk_json(obj,source_url,out,depth=0):
    if depth>12:return
    if isinstance(obj,list):
        for x in obj[:1000]:_walk_json(x,source_url,out,depth+1)
        return
    if not isinstance(obj,dict):return
    typ=str(obj.get('@type') or obj.get('type') or '').lower()
    name=obj.get('name') or obj.get('title') or obj.get('productName') or obj.get('product_name')
    price=obj.get('price') or obj.get('salePrice') or obj.get('sellingPrice') or obj.get('currentPrice')
    brand=obj.get('brand')
    if isinstance(brand,dict):brand=brand.get('name')
    if name and (price is not None or 'product' in typ):
        try:
            p=float(str(price).replace(',','').replace('฿','').strip()) if price is not None and re.search(r'\d',str(price)) else None
        except:p=None
        out.append({"record_type":"ProductCandidate","product_name":str(name).strip(),"brand":str(brand or '').strip(),"price":p,
                    "currency":"THB","source_url":source_url,"source_tag":"Marketing","provenance":"embedded-json"})
    promo_words=' '.join(str(obj.get(k) or '') for k in ('promotion','promotionTitle','campaign','campaignName','offer','description'))
    if (('promotion' in typ or 'campaign' in typ) and name) or re.search(r'โปรโมชั่น|promotion|discount|coupon|คูปอง',promo_words,re.I):
        title=str(name or obj.get('promotionTitle') or obj.get('campaignName') or promo_words[:160]).strip()
        if title:
            out.append({"record_type":"PromotionCandidate","promotion_title":title,"offer":str(obj.get('description') or obj.get('offer') or '')[:1200],
                        "source_url":source_url,"source_tag":"Marketing","provenance":"embedded-json"})
    for v in obj.values():
        if isinstance(v,(dict,list)):_walk_json(v,source_url,out,depth+1)

def _embedded_json_blobs(html):
    blobs=[]
    # application/json / Next.js data scripts
    for m in re.finditer(r'<script[^>]+(?:type=["\']application/json["\']|id=["\']__NEXT_DATA__["\'])[^>]*>(.*?)</script>',html or '',re.I|re.S):
        raw=m.group(1).strip()
        if raw:
            try:blobs.append(json.loads(raw))
            except:pass
    # Some frameworks serialize state as JSON assignment.
    for pat in [r'__NEXT_DATA__\s*=\s*({.*?})\s*;?\s*</script>',r'__INITIAL_STATE__\s*=\s*({.*?})\s*;']:
        for m in re.finditer(pat,html or '',re.I|re.S):
            try:blobs.append(json.loads(m.group(1)))
            except:pass
    return blobs[:25]

def structured_data(url):
    t=time.time();label='Structured / Embedded Data';diag=[]
    r=fetch(url,timeout=12)
    if not r.get('ok'):
        return _result('structured_data',label,'failed',diagnostics=[{"url":url,"error":r.get('error')}],elapsed=time.time()-t)
    p=parse_page(r.get('final_url') or url,r.get('text') or '')
    rows=[]
    a=adapter_for(url)
    for obj in p.get('jsonld') or []:rows.extend(a.extract_from_jsonld(obj,url))
    blobs=_embedded_json_blobs(r.get('text') or '')
    embedded=[]
    for obj in blobs:_walk_json(obj,url,embedded)
    rows.extend(embedded)
    diag.append({"url":url,"jsonld_blocks":len(p.get('jsonld') or []),"embedded_json_blocks":len(blobs),"embedded_candidates":len(embedded)})
    return _result('structured_data',label,'completed',rows,1,diag,time.time()-t,[r.get('final_url') or url],
                   'Structured extraction is conservative; zero records means no recognized product/promotion object was exposed in fetched page data.')

def _date_range(text):
    # Keep the source wording; extraction is best effort and intentionally non-normalizing.
    pats=[
      r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})\s*[–-]\s*(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})',
      r'(\d{1,2}\s+(?:มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)\s+25\d{2})\s*[–-]\s*(\d{1,2}\s+(?:มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)\s+25\d{2})'
    ]
    for pat in pats:
        m=re.search(pat,text or '',re.I)
        if m:return m.group(1),m.group(2)
    return '',''

def _lotus_promotion_record(parsed,url):
    text=parsed.get('text') or '';title=(parsed.get('title') or '').strip()
    if not title or title.lower() in ('promotions','โปรโมชั่น'):return None
    start,end=_date_range(text)
    # Preserve useful terms but bound record size.
    body=re.sub(r'\s+',' ',text).strip()
    return {"record_type":"PromotionCandidate","promotion_title":title[:240],"promotion_type":"Official Lotus's promotion",
            "offer":body[:1800],"start_date":start,"end_date":end,"terms":body[:4000],"source_url":url,
            "source_tag":"Marketing","provenance":"lotus-official-promotion-surface"}

def _lotus_product_record(parsed,url):
    text=parsed.get('text') or '';title=(parsed.get('title') or '').strip()
    if not title:return None
    lines=[re.sub(r'\s+',' ',x).strip() for x in text.splitlines() if x.strip()]
    price=None;regular=None;brand='';category=''
    vals=[]
    for line in lines:
        if 'ProductDetail.Brand' in line:brand=line.split('ProductDetail.Brand',1)[-1].strip(' :')
        if 'ProductDetail.Category' in line:category=line.split('ProductDetail.Category',1)[-1].strip(' :')
        for v in re.findall(r'฿\s*(\d[\d,]*(?:\.\d+)?)',line):
            try:vals.append(float(v.replace(',','')))
            except:pass
    if vals:price=vals[0];regular=vals[1] if len(vals)>1 else None
    if price is None:return None
    return {"record_type":"ProductCandidate","product_name":title[:240],"brand":brand,"category":category,
            "price":price,"regular_price":regular,"currency":"THB","source_url":url,"source_tag":"Marketing",
            "provenance":"lotus-official-product-page"}



def _clean_product_title(title):
    title=re.sub(r'\s*\|\s*Lotus.*$','',title or '',flags=re.I)
    title=re.sub(r'\s+',' ',title).strip()
    return title[:240]


def _lotus_product_from_page(url,render_fallback=False):
    """Extract one canonical Lotus product record from an official detail URL.

    Uses multiple independent signals: visible text/meta, JSON-LD/application JSON,
    and (only when needed) browser-rendered DOM. This intentionally avoids treating
    arbitrary numbers in page text as prices unless the page itself is a product URL.
    """
    diag=[];r=fetch(url,timeout=14)
    if not r.get('ok'):
        return None,[{'url':url,'stage':'direct-fetch','status':'failed','error':r.get('error')}]
    final=r.get('final_url') or url;html=r.get('text') or '';p=parse_page(final,html)
    rec=_lotus_product_record(p,final)
    if rec:
        rec['product_name']=_clean_product_title(rec.get('product_name'))
        rec['provenance']='lotus-product-detail-visible'
        return rec,[{'url':final,'stage':'visible-text','status':'record'}]

    # E-commerce meta tags are a reliable secondary signal when visible text is thin.
    meta=p.get('meta') or {};title=_clean_product_title(meta.get('og:title') or meta.get('twitter:title') or p.get('title'))
    amount=meta.get('product:price:amount') or meta.get('og:price:amount') or meta.get('product:price')
    if title and amount and re.search(r'\d',str(amount)):
        try:price=float(re.sub(r'[^0-9.]','',str(amount)))
        except:price=None
        if price is not None:
            return {'record_type':'ProductCandidate','product_name':title,'brand':'','category':'','price':price,
                    'currency':meta.get('product:price:currency') or 'THB','source_url':final,'source_tag':'Marketing',
                    'provenance':'lotus-product-meta'},[{'url':final,'stage':'meta','status':'record'}]

    # Parse JSON-LD and framework application JSON. Prefer records with an actual price.
    rows=[];urls=[];metrics={}
    for obj in (p.get('jsonld') or []): scan_json(obj,final,rows,urls,metrics)
    for obj in json_objects(html): scan_json(obj,final,rows,urls,metrics)
    candidates=[x for x in _dedup(rows) if x.get('record_type')=='ProductCandidate' and x.get('price') is not None and x.get('product_name')]
    if candidates:
        x=dict(candidates[0]);x['product_name']=_clean_product_title(x.get('product_name'));x['source_url']=final;x['provenance']='lotus-product-structured-json'
        return x,[{'url':final,'stage':'structured-json','status':'record','candidates':len(candidates)}]

    # Last resort: rendered product detail DOM. Search engines currently expose name,
    # brand/category and price from these pages, so this is expected to recover JS-only detail.
    if render_fallback:
        br=browser_render(final,timeout=32)
        if br.get('ok') and br.get('html'):
            pp=parse_page(final,br.get('html') or '')
            rec=_lotus_product_record(pp,final)
            if rec:
                rec['product_name']=_clean_product_title(rec.get('product_name'));rec['provenance']='lotus-product-rendered-dom'
                return rec,[{'url':final,'stage':'rendered-dom','status':'record'}]
        diag.append({'url':final,'stage':'rendered-dom','status':'no-record','error':br.get('error')})
    return None,diag or [{'url':final,'stage':'product-detail','status':'no-record'}]


def _lotus_product_links_from_html(html,base):
    normalized=(html or '').replace('\\u002F','/').replace('\\/','/').replace('&amp;','&')
    out=[]
    # Absolute/relative routes in href, JSON state, client-side route objects and rendered DOM.
    pats=[r'https?://(?:www\.)?lotuss\.com/(?:th|en)/(?:smartx/)?product/[^\\s"\'<>?#]+',
          r'["\']((?:/)?(?:th|en)/(?:smartx/)?product/[^"\'<>?#]+)["\']',
          r'href=["\']([^"\']*/(?:th|en)/(?:smartx/)?product/[^"\']+)["\']']
    for i,pat in enumerate(pats):
        for m in re.finditer(pat,normalized,re.I):
            v=m.group(0) if i==0 else m.group(1)
            v=v.strip('"\' ')
            if v.startswith('http'):u=v
            else:u=urljoin(base,'/'+v.lstrip('/'))
            u=u.split('#')[0]
            if _is_lotus(u) and '/product/' in u and u not in out:out.append(u)
    for u in extract_urls(normalized,base):
        if _is_lotus(u) and '/product/' in u and u not in out:out.append(u)
    return out



def _sku_from_product_url(url):
    path=(urlparse(url).path or '').rstrip('/')
    tail=path.split('/')[-1]
    m=re.search(r'(\d{5,})$',tail)
    return m.group(1) if m else ''

def _category_slug(url):
    m=re.search(r'/(?:th|en)/category/([^/?#]+)',url or '',re.I)
    return m.group(1) if m else ''

def _lotus_category_card_rows(html,base):
    """Extract product+price facts from the rendered category DOM.

    This parser only accepts prices attached to currency/price-marked DOM elements,
    so package weights such as 700 G or 1 KG are not interpreted as prices.
    """
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []
    soup=BeautifulSoup(html or '','html.parser');rows=[];seen=set()
    for a in soup.find_all('a',href=True):
        href=a.get('href') or ''
        if '/product/' not in href:continue
        u=urljoin(base,href)
        if not _is_lotus(u):continue
        # Walk upward until enough card context is available, but avoid taking an entire page.
        node=a
        for _ in range(5):
            par=getattr(node,'parent',None)
            if not par:break
            txt=' '.join(par.stripped_strings)
            node=par
            if 25<=len(txt)<=1400 and (re.search(r'฿\s*[\d,]+(?:\.\d+)?',txt) or re.search(r'[\d,]+(?:\.\d+)?\s*บาท',txt)):
                break
        container=node
        # Product name: prefer explicit link text, image alt/title, then concise non-price text.
        name=' '.join(a.stripped_strings).strip()
        if len(name)<3:
            img=a.find('img')
            if img:name=(img.get('alt') or img.get('title') or '').strip()
        if len(name)<3:
            for el in container.find_all(['h1','h2','h3','h4','p','span'],limit=30):
                tx=' '.join(el.stripped_strings).strip()
                if 3<=len(tx)<=260 and not re.fullmatch(r'[\d\s.,฿บาท%+-]+',tx):
                    if not re.search(r'add to cart|หยิบใส่|ซื้อเลย|wishlist',tx,re.I):
                        name=tx;break
        name=_clean_product_title(name)
        if not name or len(name)<3:continue

        # Prefer elements whose class/id/attribute explicitly says "price".
        price_texts=[];regular_texts=[]
        for el in container.find_all(True,limit=80):
            attrs=' '.join([str(el.get('class') or ''),str(el.get('id') or ''),str(el.get('data-testid') or ''),str(el.get('aria-label') or '')]).lower()
            tx=' '.join(el.stripped_strings).strip()
            if not tx:continue
            if 'price' in attrs or 'ราคา' in attrs:
                if re.search(r'old|original|regular|strike|compare|was|ปกติ',attrs,re.I):regular_texts.append(tx)
                else:price_texts.append(tx)
        # Currency-marked text is accepted; bare numbers are deliberately ignored.
        whole=' '.join(container.stripped_strings)
        if not price_texts:price_texts=[whole]
        def money(vals):
            out=[]
            for tx in vals:
                for m in re.finditer(r'฿\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*บาท',tx,re.I):
                    raw=m.group(1) or m.group(2)
                    try:
                        v=float(raw.replace(',',''))
                        if 0<v<1000000:out.append(v)
                    except:pass
            return out
        prices=money(price_texts);regulars=money(regular_texts)
        if not prices:continue
        current=prices[0]
        regular=regulars[0] if regulars else (max(prices) if len(prices)>1 and max(prices)>current else None)
        sku=_sku_from_product_url(u)
        key=(sku or u,name,current)
        if key in seen:continue
        seen.add(key)
        rows.append({'record_type':'ProductCandidate','product_name':name,'brand':'','category':_category_slug(base),
                     'price':current,'regular_price':regular,'promo_price':current if regular and current<regular else None,
                     'currency':'THB','sku':sku,'source_url':u,'source_tag':'Marketing',
                     'provenance':'lotus-category-rendered-card'})
    return _dedup(rows)

def _catalog_operational_config(api_candidates):
    """Return the stable parts of the public API pattern discovered in browser traffic."""
    out={}
    for u in api_candidates or []:
        try:
            pu=urlparse(u)
            if pu.netloc!='api-o2o.lotuss.com':continue
            q=dict((k,v[-1]) for k,v in __import__('urllib.parse').parse.parse_qs(pu.query).items() if v)
            if '/product/v4/products' in pu.path and 'batch_endpoint' not in out:
                out['batch_endpoint']=f'{pu.scheme}://{pu.netloc}{pu.path}'
                out['seller_id']=q.get('seller_id') or '3'
                out['max_batch_size']=99
            if '/product/v6/search' in pu.path and 'search_endpoint' not in out:
                out['search_endpoint']=f'{pu.scheme}://{pu.netloc}{pu.path}'
        except Exception:pass
    if out:
        out['origin']='https://www.lotuss.com'
        out['discovery_method']='browser-network'
    return out

def _lotus_catalog_api_probe(seed,max_pages=3,source_id=None,progressive=True,operational_config=None):
    """Acquire Lotus product/price JSON from the public catalog API.

    Explore discovers the API from browser network traffic and returns a reusable
    operational configuration. Deep Audit/Acquire can reuse that configuration
    directly, avoiding Chrome rediscovery on every run.
    """
    diag=[];checked=[];rows=[];metrics={};api_candidates=[];network_urls=[]
    config=dict(operational_config or {})

    if config.get('batch_endpoint'):
        diag.append({'stage':'persisted-api-config','url':seed,'status':'used',
                     'batch_endpoint':config.get('batch_endpoint'),'seller_id':config.get('seller_id') or '3'})
        api_candidates=[config.get('batch_endpoint')]
    else:
        net=browser_netlog(seed,timeout=42)
        if net.get('ok') or net.get('api_candidates'):
            network_urls=net.get('network_urls') or []
            api_candidates=[u for u in (net.get('api_candidates') or []) if 'api-o2o.lotuss.com' in u and '/product/' in u]
            config=_catalog_operational_config(api_candidates)
            diag.append({'stage':'browser-network','url':seed,'status':'captured','network_urls':len(network_urls),
                         'product_api_candidates':len(api_candidates),'browser':net.get('exe'),
                         'operational_config':config,'error':net.get('stderr') or net.get('error')})
        else:
            diag.append({'stage':'browser-network','url':seed,'status':'failed','error':net.get('error')})

    # Preserve real observed read-only endpoints as verification probes when Explore is discovering.
    ordered=[]
    if not operational_config:
        for pat in ('/product/v6/search','/product/v4/products','/product/v4/categories'):
            ordered.extend([u for u in api_candidates if pat in u and u not in ordered])
        ordered.extend([u for u in api_candidates if u not in ordered])

    batch_endpoint=config.get('batch_endpoint')
    seller_id=str(config.get('seller_id') or '3')
    sitemap_total=None;batch_skus=[]
    if batch_endpoint:
        try:
            sm=robots_sitemaps(seed,max_sitemaps=max(16,min(34,max_pages*5)))
            products=sm.get('product_urls') or [];sitemap_total=len(products)
            # One public batch request supports up to 99 SKUs. Explore samples at most
            # two batches; operational runs can progress through up to 10 batches/run.
            batch_size=max(1,min(99,int(config.get('max_batch_size') or 99)))
            batch_requests=max(1,min(10 if progressive else 2,max(1,int(max_pages))))
            wanted=batch_size*batch_requests;offset=max(0,int(config.get('sku_offset') or 0))
            if progressive and source_id and products and 'sku_offset' not in config:
                try:
                    from operations_store import states
                    st=states().get(source_id) or {};runs=max(0,int(st.get('total_runs') or 0)-1)
                    offset=(runs*wanted)%len(products)
                except Exception:offset=0
            offset=offset%len(products) if products else 0
            sample=products[offset:offset+wanted]
            if len(sample)<wanted and offset:sample+=products[:wanted-len(sample)]
            for u in sample:
                sku=_sku_from_product_url(u)
                if sku and sku not in batch_skus:batch_skus.append(sku)

            batches=[]
            for i in range(0,len(batch_skus),batch_size):
                group=batch_skus[i:i+batch_size]
                if not group:continue
                batches.append(f"{batch_endpoint}?sku={','.join(group)}&page=1&limit={batch_size}&seller_id={seller_id}")
            ordered=batches+ordered
        except Exception as e:
            diag.append({'stage':'sitemap-sku-batch','status':'failed','error':f'{type(e).__name__}: {e}'})

    headers={'Origin':config.get('origin') or 'https://www.lotuss.com','Referer':seed}
    probed=probe_json_endpoints(ordered,max_endpoints=max(4,min(20,max_pages*4)),headers=headers)
    checked=probed.get('urls_checked') or [];diag.extend(probed.get('diagnostics') or []);metrics=probed.get('metrics') or {}
    rows=[r for r in _dedup(probed.get('rows') or [])
          if r.get('record_type')=='ProductCandidate' and r.get('product_name') and r.get('price') is not None]

    # Preserve the canonical product page as provenance; keep the API request separately.
    for r in rows:
        r['provenance']='lotus-public-catalog-api'
        if not r.get('api_source_url'):
            if 'api-o2o.lotuss.com' in (r.get('source_url') or ''):r['api_source_url']=r.get('source_url')
        if not r.get('source_url') or 'api-o2o.lotuss.com' in (r.get('source_url') or ''):
            key=r.get('sku') or r.get('product_id')
            if key:r['source_url']='https://www.lotuss.com/th/product/'+str(key)

    return {'rows':rows,'diagnostics':diag,'urls_checked':checked,'metrics':metrics,'api_candidates':ordered,
            'network_urls':network_urls,'sitemap_total':sitemap_total,'batch_skus':batch_skus,
            'operational_config':config}


def lotus_catalog_api(url,max_pages=3):
    t0=time.time();label='Lotus Catalog API'
    if not _is_lotus(url):return _result('lotus_catalog_api',label,'not-applicable',elapsed=time.time()-t0)
    seed=url if ('/category/' in url or '/search/' in url) else 'https://www.lotuss.com/th/category/meat?sort=relevance%3ADESC'
    x=_lotus_catalog_api_probe(seed,max_pages=max_pages,progressive=False)
    rows=x.get('rows') or [];metrics=x.get('metrics') or {};sitemap_total=x.get('sitemap_total')
    tested=max(1,len(x.get('batch_skus') or []));success_pct=round(100*len(rows)/tested,1) if tested else 0
    return _result('lotus_catalog_api',label,'completed',rows,len(x.get('urls_checked') or []),x.get('diagnostics'),time.time()-t0,
      x.get('urls_checked') or [],
      'Uses the exact Lotus browser network to discover public product endpoints, then performs bounded read-only JSON requests.',
      {'api_candidates':len(x.get('api_candidates') or []),'network_urls':len(x.get('network_urls') or []),
       'api_product_records':len(rows),'batch_skus_tested':len(x.get('batch_skus') or []),
       'api_materialization_success_pct':success_pct,
       'reported_total':metrics.get('reported_total'),'reported_pages':metrics.get('reported_pages'),
       'api_schema':metrics.get('api_schema'),
       'full_catalog_product_urls_from_sitemap':sitemap_total,
       'estimated_extractable_records_low':len(rows),
       'estimated_extractable_records_high':sitemap_total or metrics.get('reported_total') or len(rows) or None,
       'operational_config':x.get('operational_config') or {},
       'confidence':'high' if rows and success_pct>=80 and sitemap_total else 'medium' if rows else 'low',
       'data_fields':['SKU','product name','brand','category','current price','regular price','member price',
                      'promotion price','availability','stock','weight/unit','image','source URL'],
       'basis':'official Lotus browser-network catalog endpoints + exact O2O product JSON schema mapping'})

def lotus_catalog_api_materialize(url,max_pages=8,source_id=None,operational_config=None):
    seed=url if ('/category/' in url or '/search/' in url) else 'https://www.lotuss.com/th/category/meat?sort=relevance%3ADESC'
    x=_lotus_catalog_api_probe(seed,max_pages=max_pages,source_id=source_id,progressive=True,
                               operational_config=operational_config)
    # If a persisted endpoint stops yielding data, one bounded rediscovery is allowed.
    # Diagnostics make this explicit; no hidden legacy crawler fallback occurs.
    if operational_config and not (x.get('rows') or []):
        refreshed=_lotus_catalog_api_probe(seed,max_pages=max_pages,source_id=source_id,progressive=True,
                                           operational_config=None)
        refreshed.setdefault('diagnostics',[]).insert(0,{'stage':'persisted-api-config','status':'refresh-triggered',
          'reason':'Persisted API configuration returned zero product records; browser-network discovery was repeated.'})
        return refreshed
    return x


def category_product_materialize(url,max_pages=8):
    """Operational product/price materializer used by Deep Audit/Acquire.
    Prefer rendered category cards (where name+price are shown together), then fill
    gaps with canonical product-detail extraction. This is intentionally separate
    from Explore's bounded reporting sample.
    """
    seed=url if '/category/' in (url or '') else 'https://www.lotuss.com/th/category/meat?sort=relevance%3ADESC'
    diag=[];rows=[];links=[]
    br=browser_render(seed,timeout=42)
    if br.get('ok') and br.get('html'):
        html=br.get('html') or ''
        rows.extend(_lotus_category_card_rows(html,seed))
        links.extend(_lotus_product_links_from_html(html,seed))
        diag.append({'stage':'category-rendered-materialize','url':seed,'status':'fetched',
                     'card_records':len(rows),'product_urls':len(links),'browser':br.get('exe')})
    else:
        diag.append({'stage':'category-rendered-materialize','url':seed,'status':'failed','error':br.get('error')})
    # Direct category HTML can expose additional product URLs even when cards are JS-rendered.
    rr=fetch(seed,timeout=14)
    if rr.get('ok'):links.extend(_lotus_product_links_from_html(rr.get('text') or '',rr.get('final_url') or seed))
    links=uniq(links)
    wanted=max(1,int(max_pages))
    if len(rows)<wanted:
        known={r.get('source_url') for r in rows}
        for i,u in enumerate([x for x in links if x not in known][:wanted-len(rows)]):
            rec,dd=_lotus_product_from_page(u,render_fallback=(i<3));diag.extend(dd)
            if rec:rows.append(rec)
    return {'rows':_dedup(rows)[:max(wanted,len(rows))],'diagnostics':diag,'urls_checked':[seed]+links[:wanted],
            'category_url':seed,'category_product_urls':len(links)}

def official_surfaces_materialize(max_pages=8):
    """Operational promotion materializer: collect visible official My Lotus's cards
    from several official surfaces, then enrich with detail pages when available.
    """
    seeds=['https://my.lotuss.com/promotions/th','https://my.lotuss.com/promotions/th?category=mylotuss',
           'https://my.lotuss.com/promotions/th?category=promotion','https://my.lotuss.com/promotions/th?category=activities',
           'https://my.lotuss.com/search/Promotion/th']
    rows=[];diag=[];links=[];checked=[]
    for u in seeds:
        rr=fetch(u,timeout=12);checked.append(u)
        if not rr.get('ok'):
            diag.append({'url':u,'status':'failed','error':rr.get('error')});continue
        html=rr.get('text') or '';final=rr.get('final_url') or u
        rows.extend(visible_promotion_items(html,final));links.extend(_promotion_links(html,final))
        diag.append({'url':u,'status':'fetched','visible_items':len(visible_promotion_items(html,final))})
    for u in uniq(links)[:max(2,min(20,max_pages))]:
        rr=fetch(u,timeout=12);checked.append(u)
        if rr.get('ok'):
            rec=_lotus_promotion_record(parse_page(rr.get('final_url') or u,rr.get('text') or ''),rr.get('final_url') or u)
            if rec:rows.append(rec)
    # Normalize listing candidates to repository-ready PromotionCandidate records.
    out=[]
    for r in _dedup(rows):
        if r.get('record_type')=='PromotionCandidate':out.append(r)
        elif r.get('record_type')=='PromotionListingItemCandidate' and r.get('promotion_title'):
            out.append({'record_type':'PromotionCandidate','promotion_title':r.get('promotion_title'),
                        'promotion_type':'Official promotion listing','offer':'','terms':'',
                        'source_url':r.get('source_url'),'source_tag':'Marketing',
                        'provenance':r.get('provenance') or 'lotus-promotion-listing-card'})
    return {'rows':_dedup(out),'diagnostics':diag,'urls_checked':checked}

def category_product_catalog(url,max_pages=3):
    t0=time.time();label='Lotus Category Product & Price Catalog'
    if not _is_lotus(url):return _result('category_product_catalog',label,'not-applicable',elapsed=time.time()-t0)
    diag=[];category_seeds=[];sitemap_products=[];sitemap_categories=[]
    # If the user supplies a category URL, respect it exactly. Otherwise use a proven
    # category seed plus official category sitemap discovery so Explore can benchmark
    # product extraction without depending on the homepage exposing catalog links.
    if '/category/' in url:
        category_seeds=[url]
    else:
        category_seeds=['https://www.lotuss.com/th/category/meat?sort=relevance%3ADESC']
        try:
            sm=robots_sitemaps(url,max_sitemaps=max(12,min(28,max_pages*4)))
            sitemap_products=sm.get('product_urls') or [];sitemap_categories=sm.get('category_urls') or []
            for u in sitemap_categories:
                if u not in category_seeds:category_seeds.append(u)
        except Exception as e:diag.append({'stage':'sitemap-seed','status':'failed','error':f'{type(e).__name__}: {e}'})

    category_links=[];rendered_count=0;category_checked=[];category_rows=[];api_rows=[];reported_total=None
    category_limit=1 if '/category/' in url else min(3,max(1,max_pages))
    for seed in category_seeds[:category_limit]:
        category_checked.append(seed)
        # Direct HTML is cheap and sometimes already carries route state.
        rr=fetch(seed,timeout=14)
        if rr.get('ok'):
            direct_html=rr.get('text') or '';direct=_lotus_product_links_from_html(direct_html,rr.get('final_url') or seed)
            category_links.extend(direct)
            cr=[];cu=[];cm={}
            for obj in json_objects(direct_html):scan_json(obj,rr.get('final_url') or seed,cr,cu,cm)
            category_rows.extend([x for x in cr if x.get('record_type')=='ProductCandidate' and x.get('price') is not None])
            if cm.get('reported_total'):reported_total=max(int(reported_total or 0),int(cm.get('reported_total') or 0))
            diag.append({'url':seed,'stage':'category-direct','status':'fetched','product_urls':len(direct),'structured_products':len(category_rows),'reported_total':cm.get('reported_total')})
        else:diag.append({'url':seed,'stage':'category-direct','status':'failed','error':rr.get('error')})
        # Category pages are client-rendered; render specifically to reveal product cards.
        br=browser_render(seed,timeout=38)
        if br.get('ok'):
            rendered_count+=1;rendered_html=br.get('html') or ''
            links=_lotus_product_links_from_html(rendered_html,seed)
            category_links.extend(links)
            card_rows=_lotus_category_card_rows(rendered_html,seed)
            category_rows.extend(card_rows)
            cr=[];cu=[];cm={}
            for obj in json_objects(rendered_html):scan_json(obj,seed,cr,cu,cm)
            category_rows.extend([x for x in cr if x.get('record_type')=='ProductCandidate' and x.get('price') is not None])
            if cm.get('reported_total'):reported_total=max(int(reported_total or 0),int(cm.get('reported_total') or 0))
            diag.append({'url':seed,'stage':'category-rendered','status':'fetched','product_urls':len(links),'rendered_card_products':len(card_rows),'structured_products':len(cr),'reported_total':cm.get('reported_total'),'browser':br.get('exe')})
        else:diag.append({'url':seed,'stage':'category-rendered','status':'failed','error':br.get('error')})

    category_links=uniq(category_links);category_rows=_dedup(category_rows)
    # When the rendered DOM still hides card links, inspect the category page's own XHR/fetch traffic.
    # Only public official endpoints are probed; this is a bounded GET fallback.
    if len(category_links)<4 and category_seeds:
        try:
            net=browser_netlog(category_seeds[0],timeout=40)
            api=[u for u in (net.get('api_candidates') or []) if _is_lotus(u)]
            probed=probe_json_endpoints(api,max_endpoints=max(8,min(20,max_pages*3)))
            api_rows=_dedup([x for x in (probed.get('rows') or []) if x.get('record_type')=='ProductCandidate' and x.get('price') is not None])
            mm=probed.get('metrics') or {}
            if mm.get('reported_total'):reported_total=max(int(reported_total or 0),int(mm.get('reported_total') or 0))
            diag.append({'url':category_seeds[0],'stage':'category-network-api','status':'completed','api_candidates':len(api),'product_records':len(api_rows),'reported_total':mm.get('reported_total')})
            diag.extend(probed.get('diagnostics') or [])
        except Exception as e:diag.append({'stage':'category-network-api','status':'failed','error':f'{type(e).__name__}: {e}'})
    # If DOM discovery is unexpectedly empty, still prove the product-detail materializer
    # against official product sitemap URLs. This is a fallback, not a claim about category membership.
    detail_urls=list(category_links)
    if not detail_urls:
        if not sitemap_products:
            try:sitemap_products=robots_sitemaps(url,max_sitemaps=max(14,min(30,max_pages*5))).get('product_urls') or []
            except Exception:pass
        detail_urls=sitemap_products[:max(8,min(24,max_pages*3))]
        if detail_urls:diag.append({'stage':'product-sitemap-fallback','status':'used','product_urls':len(detail_urls)})

    sample_n=max(8,min(40,max_pages*3))
    selected=detail_urls[:sample_n];rows=_dedup(category_rows+api_rows);detail_success=0
    # Render fallback only for a small tail to cap latency; most product detail pages should
    # materialize from direct/structured signals once their URLs are known.
    for i,u in enumerate(selected):
        rec,dd=_lotus_product_from_page(u,render_fallback=(i<min(4,max_pages)))
        diag.extend(dd)
        if rec:rows.append(rec);detail_success+=1
    rows=_dedup(rows)
    rate=(detail_success/len(selected)) if selected else 0.0
    category_potential=len(category_links)
    full_catalog=len(sitemap_products)
    low=max(len(rows),round(category_potential*rate) if category_potential else 0)
    high=reported_total or (category_potential if category_potential else (full_catalog if full_catalog else None))
    confidence='high' if category_links and rate>=0.8 else 'medium' if rows else 'low'
    note='Category DOM product URLs are materialized through official product detail pages; sitemap is only a fallback/coverage source.'
    potential={'category_urls_tested':len(category_checked),'rendered_category_pages':rendered_count,
               'category_product_urls_discovered':category_potential,'category_structured_product_records':len(category_rows),
               'category_api_product_records':len(api_rows),'reported_total':reported_total,
               'product_detail_urls_tested':len(selected),'product_detail_records_extracted':detail_success,'product_detail_success_pct':round(rate*100,1),
               'full_catalog_product_urls_from_sitemap':full_catalog or None,
               'estimated_full_catalog_extractable_records':round(full_catalog*rate) if full_catalog and selected else None,
               'estimated_extractable_records_low':low,'estimated_extractable_records_high':high,'confidence':confidence,
               'data_fields':['product name','brand','category','current price','regular price','currency','source URL'],
               'basis':'rendered official Lotus category product links + official product detail extraction; full-catalog coverage uses official product sitemap'}
    return _result('category_product_catalog',label,'completed',rows,len(category_checked)+len(selected),diag,time.time()-t0,
                   category_checked+selected,note,potential)

def _promotion_links(html,base='https://my.lotuss.com'):
    found=[]
    for m in re.finditer(r'(?:https://my\.lotuss\.com)?(/promotions/[A-Za-z0-9_-]+/(?:th|en))',html or '',re.I):
        u=urljoin(base,m.group(1))
        if u not in found and '/promotions/th' not in u and '/promotions/en' not in u:found.append(u)
    return found

def official_surfaces(url,max_pages=3):
    t=time.time();label='My Lotus’s Promotion Surface'
    if not _is_lotus(url):return _result('official_surfaces',label,'not-applicable',note='No source-specific alternate-surface adapter is registered for this host.',elapsed=time.time()-t)
    seeds=['https://my.lotuss.com/promotions/th','https://my.lotuss.com/promotions/th?category=mylotuss','https://my.lotuss.com/promotions/th?category=promotion','https://my.lotuss.com/promotions/th?category=activities','https://my.lotuss.com/search/Promotion/th']
    diag=[];rows=[];urls=[];links=[];listing_items=[]
    # Explore several official catalog/filter surfaces because card hrefs may be client-side and differ by category.
    for listing in seeds[:max(2,min(len(seeds),max_pages))]:
        r=fetch(listing,timeout=12)
        if not r.get('ok'):
            diag.append({'url':listing,'status':'fetch-failed','error':r.get('error')});continue
        final=r.get('final_url') or listing;urls.append(final);p=parse_page(final,r.get('text') or '')
        lr=visible_promotion_items(r.get('text') or '',final);rows.extend(lr);listing_items.extend([x.get('promotion_title') for x in lr])
        links += [x.get('url') for x in p.get('links') or [] if '/promotions/' in (x.get('url') or '')]
        links += _promotion_links(r.get('text') or '',final)
        links += [u for u in extract_urls(r.get('text') or '',final) if 'my.lotuss.com' in u and '/promotions/' in u]
        diag.append({'url':listing,'status':'fetched','visible_listing_items':len(lr),'raw_candidate_links':len(links)})
    detail=[]
    for u in links:
        if u and u not in detail and re.search(r'/promotions/[^/?#]+/(?:th|en)',u,re.I):detail.append(u)
    # Fetch bounded detail sample when actual detail URLs are exposed.
    for u in detail[:max(2,min(max_pages,8))]:
        rr=fetch(u,timeout=12);urls.append(u)
        if not rr.get('ok'):diag.append({'url':u,'status':'fetch-failed','error':rr.get('error')});continue
        pp=parse_page(rr.get('final_url') or u,rr.get('text') or '');rec=_lotus_promotion_record(pp,rr.get('final_url') or u)
        if rec:rows.append(rec)
        diag.append({'url':u,'status':'fetched','record':bool(rec)})
    rows=_dedup(rows);visible=len(set(x for x in listing_items if x))
    if not rows:
        rows.append({'record_type':'PromotionCatalogCandidate','title':"My Lotus's Promotions",'source_url':seeds[0],'text':'Official promotion catalog was reachable but no structured/detail item was recognized.','source_tag':'Marketing','provenance':'lotus-official-promotion-listing'})
    lower=max(visible,len(detail),sum(1 for x in rows if x.get('record_type')=='PromotionCandidate'))
    return _result('official_surfaces',label,'completed',rows,len(urls),diag,time.time()-t,urls,
      "Tests the main My Lotus's listing plus category/search surfaces, then detail pages when URLs are exposed.",
      {'discovered_urls':len(detail),'visible_listing_items':visible,'estimated_extractable_records_low':lower,'estimated_extractable_records_high':max(lower,len(detail)) if lower else None,'confidence':'medium' if lower else 'low','data_fields':['campaign title','promotion description','validity period','eligibility','discount / offer','terms & conditions','participating brands / stores'],'basis':'deduplicated visible promotion cards and detail URLs across multiple official My Lotus’s listing/category/search surfaces'})

def product_surface(url,max_pages=3):
    t=time.time();label='Lotus Product / Price Surface'
    if not _is_lotus(url):return _result('product_surface',label,'not-applicable',note='Current search-assisted extraction rules are implemented for Lotus\'s official domains.',elapsed=time.time()-t)
    queries=["site:lotuss.com/th/product Lotus's product", "site:lotuss.com/th/product ProductDetail.Brand ProductDetail.Category"]
    candidates=[];diag=[]
    for q in queries:
        try:
            rs=search_web(q,limit=6,timeout=12);diag.append({"query":q,"status":"ok","results":len(rs)})
            for x in rs:
                u=x.get('url') or ''
                h=_host(u)
                if (h=='lotuss.com' or h.endswith('.lotuss.com')) and u not in candidates:candidates.append(u)
        except Exception as e:diag.append({"query":q,"status":"error","error":f"{type(e).__name__}: {e}"})
    # Keep a mixed bounded sample: product and promotion detail URLs.
    products=[u for u in candidates if '/product/' in u]
    selected=products[:max(2,min(max_pages*2,12))]
    rows=[];urls=[]
    for u in selected:
        rr=fetch(u,timeout=12);urls.append(u)
        if not rr.get('ok'):diag.append({"url":u,"status":"fetch-failed","error":rr.get('error')});continue
        pp=parse_page(rr.get('final_url') or u,rr.get('text') or '')
        rec=None
        if '/product/' in u:
            rec=_lotus_product_record(pp,rr.get('final_url') or u)
            # JSON-LD fallback if visible product text isn't enough.
            if not rec:
                norm=normalize_acquisition(rr.get('final_url') or u,{"title":pp.get('title'),"text":pp.get('text'),"jsonld":pp.get('jsonld')})
                cand=[x for x in norm.get('records') or [] if x.get('record_type')=='ProductCandidate']
                if cand:rows.extend(cand[:3])
        else:rec=None
        if rec:rows.append(rec)
        diag.append({"url":u,"status":"fetched","record":bool(rec)})
    status='completed' if any(d.get('status')=='ok' for d in diag if 'query' in d) else 'failed'
    return _result('product_surface',label,status,rows,len(urls),diag,time.time()-t,urls,
                   'Product discovery uses the public index to find official Lotus’s product pages; records are extracted only from lotuss.com.', potential={"discovered_urls":len(products),"estimated_extractable_records_low":len(rows),"estimated_extractable_records_high":len(products),"confidence":"medium" if products else "low","data_fields":["product name","brand","category","current price","regular price","promotion text","source URL"],"basis":"unique official product detail URLs discoverable during Explore; this is a lower-bound discovery sample, not the full catalog size"})

def corporate_campaigns(url,max_pages=3):
    t=time.time();label='Lotus Corporate Campaign Surface'
    if not _is_lotus(url):return _result('corporate_campaigns',label,'not-applicable',elapsed=time.time()-t)
    seeds=['https://corporate.lotuss.com/en/promotions/lotuss/','https://corporate.lotuss.com/promotions/lotuss-go-fresh/','https://corporate.lotuss.com/en/promotions/e-catalog/']
    rows=[];urls=[];diag=[];detail=[]
    for seed in seeds:
        r=fetch(seed,timeout=12)
        if not r.get('ok'):diag.append({'url':seed,'status':'fetch-failed','error':r.get('error')});continue
        urls.append(r.get('final_url') or seed);p=parse_page(r.get('final_url') or seed,r.get('text') or '')
        for x in p.get('links') or []:
            u=x.get('url') or ''
            if 'corporate.lotuss.com' in _host(u) and '/promotions/' in u and u.rstrip('/') not in [z.rstrip('/') for z in seeds] and u not in detail:detail.append(u)
        diag.append({'url':seed,'status':'fetched','detail_links_found':len(detail)})
    for u in detail[:max(2,min(max_pages*2,10))]:
        rr=fetch(u,timeout=12)
        if not rr.get('ok'):continue
        urls.append(u);pp=parse_page(rr.get('final_url') or u,rr.get('text') or '')
        rec=_lotus_promotion_record(pp,rr.get('final_url') or u)
        if rec:
            rec['provenance']='lotus-corporate-campaign';rows.append(rec)
    return _result('corporate_campaigns',label,'completed',rows,len(urls),diag,time.time()-t,urls,
        'Corporate Lotus’s pages provide campaign discovery and detailed campaign conditions.',potential={'discovered_urls':len(detail),'estimated_extractable_records_low':len(rows),'estimated_extractable_records_high':len(detail),'confidence':'medium' if detail else 'low','data_fields':['campaign title','campaign period','mechanics','participating products / brands','channel / store scope','terms & conditions'],'basis':'unique promotion detail links exposed by three official corporate campaign indexes'})

def search_assisted(url,max_pages=3):
    t=time.time();label='Search-assisted Coverage Discovery'
    if not _is_lotus(url):return _result('search_assisted',label,'not-applicable',elapsed=time.time()-t)
    queries=["site:lotuss.com/th/product Lotus's",'site:my.lotuss.com/promotions/th Lotus','site:corporate.lotuss.com/promotions/lotuss Lotus']
    buckets={'product':set(),'promotion':set(),'corporate_campaign':set()};diag=[]
    for q in queries:
        try:
            rs=search_web(q,limit=20,timeout=12);diag.append({'query':q,'status':'ok','results':len(rs)})
            for x in rs:
                u=x.get('url') or ''
                if '/th/product/' in u:buckets['product'].add(u)
                elif 'my.lotuss.com' in u and '/promotions/' in u:buckets['promotion'].add(u)
                elif 'corporate.lotuss.com' in u and '/promotions/' in u:buckets['corporate_campaign'].add(u)
        except Exception as e:diag.append({'query':q,'status':'error','error':f'{type(e).__name__}: {e}'})
    total=sum(map(len,buckets.values()))
    pot={'discovered_urls':total,'by_surface':{k:len(v) for k,v in buckets.items()},'estimated_extractable_records_low':None,'estimated_extractable_records_high':None,'confidence':'low','data_fields':['product / price records','promotion records','corporate campaign records'],'basis':'public-index discovery. This establishes a discoverable lower bound; it cannot prove the full site total.'}
    return _result('search_assisted',label,'completed',[],0,diag,time.time()-t,[],
        'Coverage discovery estimates what official URLs are discoverable without pretending the search index is a complete catalog.',potential=pot)


def sitemap_discovery(url,max_pages=3):
    t=time.time();label='Robots / Sitemap Discovery'
    if not _is_lotus(url):return _result('sitemap_discovery',label,'not-applicable',elapsed=time.time()-t)
    x=robots_sitemaps(url,max_sitemaps=max(8,min(30,max_pages*5)))
    products=x.get('product_urls') or [];promos=x.get('promotion_urls') or []
    rows=[{'record_type':'ProductURLCandidate','title':u.rsplit('/',1)[-1],'source_url':u,'source_tag':'Product','provenance':'lotus-sitemap'} for u in products[:8]]
    rows += [{'record_type':'PromotionURLCandidate','title':u.rsplit('/',2)[-2],'source_url':u,'source_tag':'Marketing','provenance':'lotus-sitemap'} for u in promos[:8]]
    return _result('sitemap_discovery',label,'completed',rows,len(x.get('sitemaps') or []),x.get('diagnostics'),time.time()-t,x.get('sitemaps') or [],
      'URL-coverage evidence from official robots/sitemaps; URL candidates are not yet acquired business facts.',
      {'discovered_urls':len(x.get('urls') or []),'by_surface':{'product':len(products),'promotion_or_campaign':len(promos)},'estimated_extractable_records_low':0,'estimated_extractable_records_high':len(products)+len(promos) or None,'confidence':'high' if (products or promos) else 'low','data_fields':['official detail URL','surface type'],'basis':'official robots.txt and sitemap XML'})

def app_bundle_mining(url,max_pages=3):
    t=time.time();label='JavaScript / App Bundle Mining'
    if not _is_lotus(url):return _result('app_bundle_mining',label,'not-applicable',elapsed=time.time()-t)
    rows=[];candidate=[];apis=[];diag=[];scripts=[];metrics={}
    for seed in uniq([url,'https://my.lotuss.com/promotions/th']):
        x=script_bundle_mining(seed,max_scripts=max(8,min(24,max_pages*4)))
        rows.extend(x.get('rows') or []);rows.extend(x.get('listing_rows') or []);candidate.extend(x.get('candidate_urls') or []);apis.extend(x.get('api_candidates') or []);diag.extend(x.get('diagnostics') or []);scripts.extend(x.get('scripts') or [])
        for k,v in (x.get('metrics') or {}).items():
            if isinstance(v,(int,float)):metrics[k]=max(metrics.get(k,0),v)
    relevant=[u for u in uniq(candidate) if _is_lotus(u) and ('/product/' in u or '/promotions/' in u)]
    potential=max(len(relevant),metrics.get('reported_total',0),metrics.get('max_array_len',0))
    return _result('app_bundle_mining',label,'completed',rows,len(uniq(scripts)),diag,time.time()-t,uniq(scripts)[:30],
      'Mines publicly delivered application assets; API-like strings remain candidates until a safe probe succeeds.',
      {'discovered_urls':len(relevant),'api_candidates':len(uniq(apis)),'reported_total':metrics.get('reported_total'),'largest_embedded_array':metrics.get('max_array_len'),'estimated_extractable_records_low':len(_dedup(rows)),'estimated_extractable_records_high':potential or None,'confidence':'high' if metrics.get('reported_total') else ('medium' if relevant or rows else 'low'),'data_fields':['product/promotion objects','detail URLs','API route candidates','pagination/count metadata'],'basis':'official HTML, application JSON and JavaScript bundles'})

def browser_rendered(url,max_pages=3):
    t=time.time();label='Browser-rendered DOM';rows=[];urls=[];diag=[];pages=0;available=None
    if not _is_lotus(url):return _result('browser_rendered',label,'not-applicable',elapsed=time.time()-t)
    for seed in [url if 'my.lotuss.com' in url else 'https://my.lotuss.com/promotions/th']:
        x=browser_render(seed,timeout=28);available=x.get('available',False)
        if not available:diag.append({'url':seed,'status':'unavailable','error':x.get('error')});break
        pages+=1;rows.extend(x.get('rows') or []);urls.extend([u for u in x.get('urls') or [] if _is_lotus(u)]);diag.append({'url':seed,'status':'rendered' if x.get('ok') else 'render-failed','browser':x.get('exe'),'dom_bytes':len(x.get('html') or ''),'lotus_urls':len(x.get('urls') or []),'error':x.get('error') or x.get('stderr')})
    relevant=[u for u in uniq(urls) if '/product/' in u or '/promotions/' in u]
    return _result('browser_rendered',label,'completed' if available else 'unavailable',rows,pages,diag,time.time()-t,relevant[:30],
      'Local Chrome/Edge JavaScript-rendered fallback.',{'discovered_urls':len(relevant),'estimated_extractable_records_low':len(_dedup(rows)),'estimated_extractable_records_high':max(len(relevant),len(_dedup(rows))) or None,'confidence':'medium' if relevant or rows else 'low','data_fields':['rendered promotion cards','rendered detail URLs','client-side content'],'basis':'DOM after JavaScript execution'})

def browser_network(url,max_pages=3):
    t=time.time();label='Browser Network / API Discovery';diag=[];network=[];apis=[];pages=0;available=None
    if not _is_lotus(url):return _result('browser_network',label,'not-applicable',elapsed=time.time()-t)
    for seed in [url if '/search/' in url else 'https://www.lotuss.com/th/search/%E0%B8%99%E0%B8%A1']:
        x=browser_netlog(seed,timeout=30);available=x.get('available',False)
        if not available:diag.append({'url':seed,'status':'unavailable','error':x.get('error')});break
        pages+=1;network.extend(x.get('network_urls') or []);apis.extend(x.get('api_candidates') or []);diag.append({'url':seed,'status':'captured' if x.get('ok') else 'capture-failed','browser':x.get('exe'),'network_urls':len(x.get('network_urls') or []),'api_candidates':len(x.get('api_candidates') or []),'error':x.get('error') or x.get('stderr')})
    apis=uniq(apis);network=uniq(network);rows=[{'record_type':'EndpointCandidate','title':u[:220],'source_url':u,'source_tag':'Technical','provenance':'lotus-browser-netlog'} for u in apis[:12]]
    return _result('browser_network',label,'completed' if available else 'unavailable',rows,pages,diag,time.time()-t,apis[:30],
      'Endpoint candidates are not treated as data until a bounded JSON probe succeeds.',{'discovered_urls':len(network),'api_candidates':len(apis),'estimated_extractable_records_low':0,'estimated_extractable_records_high':None,'confidence':'medium' if apis else 'low','data_fields':['XHR/fetch URL','catalog/content/search endpoint candidate'],'basis':'local Chrome/Edge network log'})

def api_json_probe(url,max_pages=3):
    t=time.time();label='Discovered JSON/API Probe';diag=[];candidates=[]
    if not _is_lotus(url):return _result('api_json_probe',label,'not-applicable',elapsed=time.time()-t)
    for seed in uniq([url,'https://my.lotuss.com/promotions/th']):
        x=script_bundle_mining(seed,max_scripts=max(6,min(16,max_pages*3)));candidates.extend(x.get('api_candidates') or []);diag.extend(x.get('diagnostics') or [])
    candidates=[u for u in uniq(candidates) if _is_lotus(u) and not any(x in u for x in ('{','}','<','>'))]
    probed=probe_json_endpoints(candidates,max_endpoints=max(6,min(18,max_pages*3)));diag.extend(probed.get('diagnostics') or []);metrics=probed.get('metrics') or {};rows=probed.get('rows') or [];total=metrics.get('reported_total') or metrics.get('max_array_len')
    return _result('api_json_probe',label,'completed',rows,len(probed.get('urls_checked') or []),diag,time.time()-t,probed.get('urls_checked') or [],
      'Read-only GET probes only; no authentication bypass or mutation.',{'discovered_urls':len(candidates),'api_candidates_probed':len(probed.get('urls_checked') or []),'reported_total':metrics.get('reported_total'),'reported_pages':metrics.get('reported_pages'),'estimated_extractable_records_low':len(_dedup(rows)),'estimated_extractable_records_high':total,'confidence':'high' if metrics.get('reported_total') and rows else ('medium' if rows else 'low'),'data_fields':['product name','brand','price','promotion','API pagination/count metadata'],'basis':'successful JSON responses from official endpoints discovered in application assets; browser-network candidates are reported separately'})

def multi_index(url,max_pages=3):
    t=time.time();label='Multi-index Official URL Discovery'
    if not _is_lotus(url):return _result('multi_index',label,'not-applicable',elapsed=time.time()-t)
    x=multi_search(["site:lotuss.com/th/product Lotus's","site:my.lotuss.com/promotions Lotus's","site:corporate.lotuss.com/promotions Lotus's"],limit=max(20,min(80,max_pages*12)));urls=x.get('urls') or []
    prod=[u for u in urls if '/product/' in u];promo=[u for u in urls if 'my.lotuss.com' in u and '/promotions/' in u];corp=[u for u in urls if 'corporate.lotuss.com' in u and '/promotions/' in u]
    rows=[{'record_type':'OfficialURLCandidate','title':u.rsplit('/',1)[-1] or u,'source_url':u,'source_tag':'Discovery','provenance':'multi-public-index'} for u in urls[:12]]
    return _result('multi_index',label,'completed',rows,0,x.get('diagnostics') or [],time.time()-t,urls[:30],
      'Index count is only a lower bound, never the claimed full catalog.',{'discovered_urls':len(urls),'by_surface':{'product':len(prod),'promotion':len(promo),'corporate_campaign':len(corp)},'estimated_extractable_records_low':0,'estimated_extractable_records_high':len(urls) or None,'confidence':'low','data_fields':['official indexed detail URLs'],'basis':'deduplicated official URLs across multiple public indexes'})

def run(url,max_pages=3,techniques=None,progress_callback=None):
    selected=techniques or [x['key'] for x in TECHNIQUES]
    known={x['key'] for x in TECHNIQUES};selected=[x for x in selected if x in known]
    funcs={
      'basic_crawler':lambda:basic_crawler(url,max_pages),
      'structured_data':lambda:structured_data(url),
      'official_surfaces':lambda:official_surfaces(url,max_pages),
      'product_surface':lambda:product_surface(url,max_pages),
      'category_product_catalog':lambda:category_product_catalog(url,max_pages),
      'lotus_catalog_api':lambda:lotus_catalog_api(url,max_pages),
      'corporate_campaigns':lambda:corporate_campaigns(url,max_pages),
      'search_assisted':lambda:search_assisted(url,max_pages),
      'sitemap_discovery':lambda:sitemap_discovery(url,max_pages),
      'app_bundle_mining':lambda:app_bundle_mining(url,max_pages),
      'browser_rendered':lambda:browser_rendered(url,max_pages),
      'browser_network':lambda:browser_network(url,max_pages),
      'api_json_probe':lambda:api_json_probe(url,max_pages),
      'multi_index':lambda:multi_index(url,max_pages),
    }
    results=[]
    # Techniques are independent evidence paths; run them concurrently to avoid serial network latency.
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(selected)))) as ex:
        fut={ex.submit(funcs[k]):k for k in selected}
        for f in as_completed(fut):
            k=fut[f]
            try:r=f.result()
            except Exception as e:
                meta=next(x for x in TECHNIQUES if x['key']==k)
                r=_result(k,meta['label'],'failed',diagnostics=[{"error":f"{type(e).__name__}: {e}"}])
            results.append(r)
            if progress_callback:
                try:progress_callback(len(results),len(selected),r)
                except Exception:pass
    order={x['key']:i for i,x in enumerate(TECHNIQUES)};results.sort(key=lambda x:order.get(x['technique'],99))
    allrows=[]
    for x in results:allrows.extend(x.get('sample_records') or [])
    allrows=_dedup(allrows)
    pot=[{"technique":x["technique"],"label":x["label"],**(x.get("potential") or {})} for x in results if x.get("potential")]
    return {"techniques_available":TECHNIQUES,"techniques_selected":selected,"technique_results":results,"potential_coverage":pot,
            "record_count":sum(x.get('record_count',0) for x in results),
            "unique_sample_record_count":len(allrows),"record_types":_types(allrows),"sample_records":allrows[:12]}
