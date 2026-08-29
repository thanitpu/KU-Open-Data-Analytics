from __future__ import annotations
import json, os, re, shutil, subprocess, tempfile, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse, urljoin

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36'
TIMEOUT=15
MAX_BYTES=8_000_000

def host(url):
    try:return (urlparse(url).netloc or '').lower().removeprefix('www.')
    except:return ''

def lotus(url):
    h=host(url);return h=='lotuss.com' or h.endswith('.lotuss.com')
def site_family(url):
    h=host(url); parts=h.split('.')
    return '.'.join(parts[-2:]) if len(parts)>=2 else h
def same_site(a,b):
    return bool(site_family(a) and site_family(a)==site_family(b))

def get(url,timeout=TIMEOUT,headers=None):
    h={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8','Accept-Language':'th-TH,th;q=0.9,en;q=0.7'}
    if headers:h.update(headers)
    try:
        req=urllib.request.Request(url,headers=h)
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read(MAX_BYTES);ct=r.headers.get('Content-Type','');enc=r.headers.get_content_charset() or 'utf-8'
            return {'ok':True,'status':getattr(r,'status',200),'final_url':r.geturl(),'content_type':ct,'text':raw.decode(enc,'replace'),'bytes':len(raw),'headers':dict(r.headers.items())}
    except Exception as e:return {'ok':False,'status':getattr(e,'code',0) or 0,'error':f'{type(e).__name__}: {e}','url':url}

def uniq(xs):
    out=[];seen=set()
    for x in xs:
        if x and x not in seen:seen.add(x);out.append(x)
    return out

def extract_urls(text,base=''):
    text=text or ''; out=[]
    # absolute and escaped absolute URLs
    normalized=text.replace('\\u002F','/').replace('\\/','/').replace('&amp;','&')
    for m in re.finditer(r'https?://[^\s"\'<>\\]+',normalized,re.I):out.append(m.group(0).rstrip('),.;'))
    # useful Lotus relative routes from raw HTML/JSON/JS
    pats=[r'["\']([^"\']*/promotions/[^"\']+)["\']',r'["\']([^"\']*/th/product/[^"\']+)["\']',r'["\']([^"\']*/product/[^"\']+)["\']']
    for pat in pats:
        for m in re.finditer(pat,normalized,re.I):
            p=m.group(1)
            if base:out.append(urljoin(base,p))
    return uniq([u.split('#')[0] for u in out if u.startswith('http')])

def visible_promotion_items(html,source_url):
    # Promotion listing cards expose descriptive image alt/title text even when href is JS-bound.
    vals=[]
    for m in re.finditer(r'<img[^>]+(?:alt|title)=["\']([^"\']{8,240})["\']',html or '',re.I):
        x=re.sub(r'\s+',' ',m.group(1)).strip()
        low=x.lower()
        if x and not any(k in low for k in ('icon','logo','sort','filter','detail','copy link','facebook','line','youtube')):vals.append(x)
    vals=uniq(vals)
    return [{'record_type':'PromotionListingItemCandidate','promotion_title':x,'source_url':source_url,'source_tag':'Marketing','provenance':'lotus-promotion-listing-card'} for x in vals[:200]]

def json_objects(text):
    out=[]
    for m in re.finditer(r'<script[^>]+(?:type=["\']application/json["\']|id=["\']__NEXT_DATA__["\'])[^>]*>(.*?)</script>',text or '',re.I|re.S):
        try:out.append(json.loads(m.group(1).strip()))
        except:pass
    return out


def lotus_catalog_product_rows(obj,source_url):
    """Parse the public Lotus O2O catalog schema observed from /product/v4/products.

    Expected shape:
      {"code":200,"data":{"products":[...],"breadcrumb":[...]}}
    Price fields are explicit API price fields, never package-size numbers.
    """
    if not isinstance(obj,dict):return []
    data=obj.get('data')
    if not isinstance(data,dict) or not isinstance(data.get('products'),list):return []

    breadcrumb=data.get('breadcrumb') or []
    category_name='';category_id='';category_path=''
    if isinstance(breadcrumb,list):
        for b in breadcrumb:
            if not isinstance(b,dict):continue
            if b.get('name'):category_name=str(b.get('name')).strip()
            if b.get('id') is not None:category_id=str(b.get('id'))
            if b.get('urlKey'):category_path=str(b.get('urlKey')).strip()
    try:
        q=urllib.parse.parse_qs(urllib.parse.urlparse(source_url).query)
        category_path=category_path or (q.get('category_path') or [''])[0]
        category_id=category_id or (q.get('category_id') or [''])[0]
        seller_id=(q.get('seller_id') or [''])[0]
    except Exception:
        seller_id=''

    def scalar(v):
        if isinstance(v,dict):
            return v.get('value') if v.get('value') is not None else v.get('amount')
        return v
    def num(v):
        v=scalar(v)
        try:
            if v is None or v=='':return None
            return float(str(v).replace(',','').replace('฿','').strip())
        except:return None

    rows=[]
    for prod in data.get('products') or []:
        if not isinstance(prod,dict):continue
        name=str(prod.get('name') or prod.get('productName') or '').strip()
        sku=str(prod.get('sku') or prod.get('id') or '').strip()
        if not name or not sku:continue

        price_range=prod.get('priceRange') or {}
        minimum=(price_range.get('minimumPrice') or {}) if isinstance(price_range,dict) else {}
        regular=num(prod.get('regularPricePerUOW'))
        final=num(prod.get('finalPricePerUOW'))
        member=num(prod.get('loyaltyMemberPricePerUOW'))
        if regular is None:regular=num((minimum.get('regularPrice') or {}).get('value') if isinstance(minimum.get('regularPrice'),dict) else minimum.get('regularPrice'))
        if final is None:final=num((minimum.get('finalPrice') or {}).get('value') if isinstance(minimum.get('finalPrice'),dict) else minimum.get('finalPrice'))
        if member is None:member=num((minimum.get('loyaltyMemberPrice') or {}).get('value') if isinstance(minimum.get('loyaltyMemberPrice'),dict) else minimum.get('loyaltyMemberPrice'))
        if member is not None and member <= 0:member=None
        current=final if final is not None else regular
        if current is None:continue

        discount=minimum.get('discount') or {}
        url_key=str(prod.get('urlKey') or sku).strip()
        canonical='https://www.lotuss.com/th/product/'+url_key
        thumb=prod.get('thumbnail') or {}
        image=(thumb.get('url') if isinstance(thumb,dict) else '') or prod.get('imageUrl') or ''
        brand=prod.get('brand') or prod.get('brandName') or ''
        if isinstance(brand,dict):brand=brand.get('name') or brand.get('title') or ''
        promotions=prod.get('promotions') or []
        if not isinstance(promotions,list):promotions=[]

        rows.append({
          'record_type':'ProductCandidate',
          'product_name':name[:300],
          'brand':str(brand or '')[:120],
          'category':category_name or category_path or '',
          'category_id':category_id,
          'category_path':category_path,
          'price':current,
          'regular_price':regular,
          'promo_price':current if regular is not None and current < regular else None,
          'member_price':member,
          'currency':'THB',
          'sku':sku,
          'product_id':prod.get('id'),
          'availability':prod.get('stockStatus'),
          'stock_on_hand':prod.get('stockOnHand'),
          'selling_type':prod.get('sellingType'),
          'weight':prod.get('weight'),
          'weight_per_piece':prod.get('weightPerPiece'),
          'unit_of_weight':prod.get('unitOfWeight'),
          'unit_of_quantity':prod.get('unitOfQuantity'),
          'discount_amount':discount.get('amountOff') if isinstance(discount,dict) else None,
          'discount_percent':discount.get('percentOff') if isinstance(discount,dict) else None,
          'promotion_count':len(promotions),
          'image_url':str(image or '')[:900],
          'seller_id':seller_id,
          'source_url':canonical,
          'api_source_url':source_url,
          'source_tag':'Product',
          'provenance':'lotus-public-catalog-api'
        })
    return rows

def scan_json(obj,source_url,rows,urls,metrics,depth=0):
    if depth>18:return
    if isinstance(obj,list):
        metrics['arrays']=metrics.get('arrays',0)+1
        metrics['max_array_len']=max(metrics.get('max_array_len',0),len(obj))
        for x in obj[:5000]:scan_json(x,source_url,rows,urls,metrics,depth+1)
        return
    if not isinstance(obj,dict):return
    for k,v in obj.items():
        kl=str(k).lower()
        if kl in ('total','totalcount','total_count','count','totalitems','totalitemsCount'.lower()) and isinstance(v,(int,float)):
            metrics['reported_total']=max(metrics.get('reported_total',0),int(v))
        if kl in ('pagecount','totalpages','total_pages','lastpage','last_page') and isinstance(v,(int,float)):
            metrics['reported_pages']=max(metrics.get('reported_pages',0),int(v))
        if isinstance(v,str):
            for u in extract_urls(v,source_url):urls.append(u)
    typ=str(obj.get('@type') or obj.get('type') or obj.get('__typename') or obj.get('entity_type') or '').lower()
    name=(obj.get('name') or obj.get('title') or obj.get('productName') or obj.get('product_name') or
          obj.get('displayName') or obj.get('display_name') or obj.get('productTitle') or obj.get('product_title'))
    price=(obj.get('price') or obj.get('sellingPrice') or obj.get('salePrice') or obj.get('currentPrice') or obj.get('finalPrice') or
           obj.get('selling_price') or obj.get('sale_price') or obj.get('current_price') or obj.get('final_price') or
           obj.get('unit_price') or obj.get('price_value'))
    regular=(obj.get('regularPrice') or obj.get('originalPrice') or obj.get('normalPrice') or obj.get('listPrice') or
             obj.get('regular_price') or obj.get('original_price') or obj.get('normal_price') or obj.get('list_price') or obj.get('rrp'))
    promo=(obj.get('promoPrice') or obj.get('promotionPrice') or obj.get('discountPrice') or
           obj.get('promo_price') or obj.get('promotion_price') or obj.get('discount_price'))
    def _price_scalar(v):
        if isinstance(v,dict):
            return v.get('value') or v.get('amount') or v.get('price') or v.get('current') or v.get('selling_price')
        if isinstance(v,list) and v and isinstance(v[0],dict):
            return _price_scalar(v[0])
        return v
    price=_price_scalar(price);regular=_price_scalar(regular);promo=_price_scalar(promo)
    offers=obj.get('offers')
    if price is None and isinstance(offers,dict):
        price=offers.get('price') or offers.get('lowPrice') or offers.get('salePrice') or offers.get('selling_price')
        regular=regular or offers.get('regularPrice') or offers.get('originalPrice') or offers.get('listPrice')
    elif price is None and isinstance(offers,list) and offers and isinstance(offers[0],dict):
        price=offers[0].get('price') or offers[0].get('lowPrice') or offers[0].get('salePrice')
        regular=regular or offers[0].get('regularPrice') or offers[0].get('originalPrice')
    brand=obj.get('brand') or obj.get('brandName') or obj.get('brand_name') or ''
    if isinstance(brand,dict):brand=brand.get('name') or brand.get('title') or ''
    category=obj.get('category') or obj.get('categoryName') or obj.get('category_name') or obj.get('categoryTitle') or ''
    if isinstance(category,dict):category=category.get('name') or category.get('title') or ''
    sku=(obj.get('sku') or obj.get('skuId') or obj.get('sku_id') or obj.get('productId') or obj.get('product_id') or '')
    availability=(obj.get('availability') or obj.get('stockStatus') or obj.get('stock_status') or obj.get('is_in_stock') or obj.get('available'))
    image=obj.get('image') or obj.get('imageUrl') or obj.get('image_url') or obj.get('thumbnail') or ''
    if isinstance(image,dict):image=image.get('url') or image.get('src') or ''
    def _num(v):
        try:
            s=re.sub(r'[^0-9.]','',str(v))
            return float(s) if s and re.search(r'\d',s) else None
        except:return None
    product_hint=('product' in typ or bool(sku) or any(k in obj for k in ('sellingPrice','selling_price','salePrice','sale_price','productName','product_name')))
    if name and (price is not None or product_hint):
        pval=_num(price);rval=_num(regular);promoval=_num(promo)
        rows.append({'record_type':'ProductCandidate','product_name':str(name)[:240],'brand':str(brand or '')[:120],
                     'category':str(category or '')[:160],'price':pval,'regular_price':rval,'promo_price':promoval,
                     'currency':str(obj.get('currency') or obj.get('priceCurrency') or 'THB')[:12],
                     'sku':str(sku or '')[:100],'availability':availability,'image_url':str(image or '')[:700],
                     'source_url':source_url,'source_tag':'Marketing','provenance':'lotus-application-json'})
    promo=' '.join(str(obj.get(k) or '') for k in ('promotionTitle','campaignName','promotion','campaign','description','offer'))
    if name and ('promotion' in typ or 'campaign' in typ) or re.search(r'โปรโมชั่น|promotion|coupon|discount|คูปอง',promo,re.I):
        title=str(name or obj.get('promotionTitle') or obj.get('campaignName') or promo[:180]).strip()
        if title:rows.append({'record_type':'PromotionCandidate','promotion_title':title[:240],'offer':str(obj.get('description') or obj.get('offer') or '')[:1800],'source_url':source_url,'source_tag':'Marketing','provenance':'lotus-application-json'})
    for v in obj.values():
        if isinstance(v,(dict,list)):scan_json(v,source_url,rows,urls,metrics,depth+1)

def robots_sitemaps(seed='https://www.lotuss.com/th',max_sitemaps=12):
    roots=['https://www.lotuss.com/robots.txt','https://www.lotuss.com/sitemap.xml','https://www.lotuss.com/sitemap_index.xml','https://www.lotuss.com/th/sitemap.xml',
           'https://my.lotuss.com/robots.txt','https://my.lotuss.com/sitemap.xml','https://corporate.lotuss.com/robots.txt','https://corporate.lotuss.com/sitemap.xml']
    checked=[]; sitemap_urls=[]; urls=[]; diag=[]
    for u in roots:
        r=get(u,timeout=10);checked.append(u)
        if not r['ok']:
            diag.append({'url':u,'status':'failed','error':r.get('error')});continue
        txt=r.get('text','');diag.append({'url':u,'status':'fetched','bytes':r.get('bytes',0)})
        if u.endswith('robots.txt'):
            for m in re.finditer(r'^\s*Sitemap:\s*(https?://\S+)',txt,re.I|re.M):sitemap_urls.append(m.group(1).strip())
        else:sitemap_urls.append(r.get('final_url') or u)
    sitemap_urls=uniq(sitemap_urls)[:max_sitemaps]
    queue=list(sitemap_urls);seen=set()
    while queue and len(seen)<max_sitemaps:
        u=queue.pop(0)
        if u in seen:continue
        seen.add(u);r=get(u,timeout=12)
        if not r['ok']:continue
        txt=r.get('text','')
        locs=re.findall(r'<loc>\s*(.*?)\s*</loc>',txt,re.I|re.S)
        for loc in locs:
            loc=loc.replace('&amp;','&').strip()
            if loc.endswith('.xml') and len(seen)+len(queue)<max_sitemaps:queue.append(loc)
            elif lotus(loc):urls.append(loc)
    urls=uniq(urls)
    products=[u for u in urls if '/product/' in u]
    promotions=[u for u in urls if '/promotions/' in u]
    categories=[u for u in urls if '/category/' in u]
    return {'checked':checked,'sitemaps':list(seen),'urls':urls,'product_urls':products,'promotion_urls':promotions,'category_urls':categories,'diagnostics':diag}

def script_bundle_mining(url='https://my.lotuss.com/promotions/th',max_scripts=14):
    r=get(url,timeout=12);diag=[]
    if not r['ok']:return {'ok':False,'diagnostics':[{'url':url,'error':r.get('error')}],'scripts':[],'candidate_urls':[],'api_candidates':[],'rows':[],'metrics':{}}
    html=r['text'];base=r.get('final_url') or url
    srcs=[]
    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']',html,re.I):srcs.append(urljoin(base,m.group(1)))
    srcs=uniq(srcs)[:max_scripts]
    urls=extract_urls(html,base);api=[];rows=[];metrics={}; scripts=[]
    for obj in json_objects(html):scan_json(obj,base,rows,urls,metrics)
    for s in srcs:
        rr=get(s,timeout=12,headers={'Accept':'*/*'});scripts.append(s)
        if not rr['ok']:
            diag.append({'url':s,'status':'failed','error':rr.get('error')});continue
        js=rr['text'];diag.append({'url':s,'status':'fetched','bytes':rr.get('bytes',0)})
        for u in extract_urls(js,base):urls.append(u)
        # API-ish strings/paths embedded in bundles.
        for m in re.finditer(r'["\']((?:https?:)?//[^"\']+|/(?:api|graphql|v\d|content|catalog|products|promotions)[^"\']{0,220})["\']',js,re.I):
            p=m.group(1).replace('\\/','/')
            if p.startswith('//'):p='https:'+p
            if p.startswith('/'):p=urljoin(base,p)
            if p.startswith('http') and same_site(p,base):api.append(p)
        # Look for route templates without claiming they are live APIs.
        for m in re.finditer(r'/(?:api|graphql|v\d|content|catalog|products|promotions)[A-Za-z0-9_?&=./{}:\-]{3,180}',js,re.I):
            p=m.group(0)
            if '{' not in p and '}' not in p:api.append(urljoin(base,p))
    return {'ok':True,'scripts':scripts,'candidate_urls':uniq(urls),'api_candidates':uniq(api),'rows':rows,'metrics':metrics,'diagnostics':diag,'listing_rows':visible_promotion_items(html,base)}

def find_chrome():
    candidates=[]
    for n in ('chrome','google-chrome','chromium','chromium-browser','msedge','microsoft-edge'):
        p=shutil.which(n)
        if p:candidates.append(p)
    if os.name=='nt':
        env=os.environ
        roots=[env.get('PROGRAMFILES'),env.get('PROGRAMFILES(X86)'),env.get('LOCALAPPDATA')]
        tails=[r'Google\Chrome\Application\chrome.exe',r'Microsoft\Edge\Application\msedge.exe']
        for root in roots:
            if root:
                for tail in tails:
                    p=str(Path(root)/tail)
                    if os.path.exists(p):candidates.append(p)
    return uniq(candidates)[0] if candidates else None

def browser_render(url,timeout=30):
    exe=find_chrome()
    if not exe:return {'ok':False,'available':False,'error':'Chrome/Edge executable not found','urls':[],'rows':[],'html':''}
    tmp=tempfile.mkdtemp(prefix='ku2d-lotus-browser-')
    cmd=[exe,'--headless=new','--no-sandbox','--disable-gpu','--no-first-run','--disable-default-apps',f'--user-data-dir={tmp}','--virtual-time-budget=6000','--dump-dom',url]
    try:
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,encoding='utf-8',errors='replace')
        html=cp.stdout or '';urls=extract_urls(html,url);rows=visible_promotion_items(html,url)
        return {'ok':cp.returncode==0 and len(html)>100,'available':True,'exe':exe,'returncode':cp.returncode,'stderr':(cp.stderr or '')[-2000:],'html':html,'urls':urls,'rows':rows}
    except Exception as e:return {'ok':False,'available':True,'exe':exe,'error':f'{type(e).__name__}: {e}','urls':[],'rows':[],'html':''}
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def browser_netlog(url,timeout=35):
    exe=find_chrome()
    if not exe:return {'ok':False,'available':False,'error':'Chrome/Edge executable not found','network_urls':[]}
    tmp=tempfile.mkdtemp(prefix='ku2d-lotus-netlog-'); net=str(Path(tmp)/'netlog.json')
    cmd=[exe,'--headless=new','--no-sandbox','--disable-gpu','--no-first-run','--disable-default-apps',f'--user-data-dir={tmp}',f'--log-net-log={net}','--net-log-capture-mode=IncludeSensitive','--virtual-time-budget=8000','--dump-dom',url]
    try:
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,encoding='utf-8',errors='replace')
        urls=[]
        if os.path.exists(net):
            raw=Path(net).read_text(encoding='utf-8',errors='ignore')
            # Chrome netlog contains request URLs in params.url / strings; scan robustly.
            urls=uniq(re.findall(r'https?://[^"\\\s]+',raw))
        urls=[u.replace('\\u0026','&').replace('\\/','/') for u in urls]
        site_urls=[u for u in urls if same_site(u,url)]
        api=[u for u in site_urls if re.search(r'/api/|graphql|catalog|product|promotion|content|search|listing|query|data',u,re.I)]
        return {'ok':cp.returncode==0,'available':True,'exe':exe,
                'network_urls':uniq(site_urls),'all_network_urls':uniq(urls),'api_candidates':uniq(api),
                'returncode':cp.returncode,'stderr':(cp.stderr or '')[-1200:]}
    except Exception as e:return {'ok':False,'available':True,'exe':exe,'error':f'{type(e).__name__}: {e}','network_urls':[],'api_candidates':[]}
    finally:shutil.rmtree(tmp,ignore_errors=True)

def probe_json_endpoints(urls,max_endpoints=12,headers=None):
    rows=[];diag=[];metrics={};used=[]
    for u in uniq(urls)[:max_endpoints]:
        r=get(u,timeout=12,headers={**{'Accept':'application/json,text/plain,*/*'},**(headers or {})})
        used.append(u)
        if not r['ok']:
            diag.append({'url':u,'status':'failed','error':r.get('error')});continue
        ct=(r.get('content_type') or '').lower();txt=r.get('text','')
        if 'json' not in ct and not txt.lstrip().startswith(('{','[')):
            diag.append({'url':u,'status':'non-json','content_type':ct});continue
        try:obj=json.loads(txt)
        except Exception as e:
            diag.append({'url':u,'status':'json-parse-failed','error':str(e)});continue
        urls2=[];before=len(rows)
        lotus_rows=lotus_catalog_product_rows(obj,u)
        if lotus_rows:
            rows.extend(lotus_rows)
            metrics['lotus_catalog_product_records']=metrics.get('lotus_catalog_product_records',0)+len(lotus_rows)
            metrics['api_schema']='lotus-o2o-product-v4'
        else:
            scan_json(obj,u,rows,urls2,metrics)
        diag.append({'url':u,'status':'json','records':len(rows)-before,
                     'schema':'lotus-o2o-product-v4' if lotus_rows else 'generic-json',
                     'reported_total':metrics.get('reported_total'),'reported_pages':metrics.get('reported_pages')})
    return {'rows':rows,'diagnostics':diag,'metrics':metrics,'urls_checked':used}

def multi_search(queries,limit=20):
    # Multiple public index fallbacks reduce single-provider fragility.
    results=[];diag=[]
    engines=[
      ('duckduckgo','https://html.duckduckgo.com/html/?q={q}'),
      ('bing','https://www.bing.com/search?q={q}&count=30'),
      ('google','https://www.google.com/search?q={q}&num=30&filter=1')]
    for q in queries:
        qq=urllib.parse.quote_plus(q)
        for name,tpl in engines:
            r=get(tpl.format(q=qq),timeout=12)
            if not r['ok']:
                diag.append({'engine':name,'query':q,'status':'failed','error':r.get('error')});continue
            urls=extract_urls(r['text'])
            # Google redirect destination extraction.
            for m in re.finditer(r'/url\?q=(https?%3A%2F%2F[^&"\']+)',r['text'] or '',re.I):
                try:urls.append(urllib.parse.unquote(m.group(1)))
                except:pass
            selected=[u for u in uniq(urls) if lotus(u)]
            diag.append({'engine':name,'query':q,'status':'ok','lotus_urls':len(selected)})
            results.extend(selected)
            if len(uniq(results))>=limit:break
    return {'urls':uniq(results)[:limit],'diagnostics':diag}
