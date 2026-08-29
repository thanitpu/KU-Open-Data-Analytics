from __future__ import annotations
import re, urllib.parse, urllib.request, json, html as html_lib, time, hashlib
from urllib.parse import urlparse, urljoin

from lotus_advanced import get, browser_netlog, browser_render, probe_json_endpoints
from actual_acquisition import parse_page

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

BIGC_DEFAULT_CATEGORIES = [
    "https://www.bigc.co.th/category/eggs-milk-dairy-products",
    "https://www.bigc.co.th/category/dry-goods-and-seasonings",
    "https://www.bigc.co.th/category/beverages",
    "https://www.bigc.co.th/category/snacks-and-confectionery",
    "https://www.bigc.co.th/category/health-and-beauty",
    "https://www.bigc.co.th/category/household-essentials",
]
BIGC_PROMOTION_SURFACES = [
    "https://www.bigc.co.th/p/campaign-special-promotions",
    "https://www.bigc.co.th/p/campaign-hl-flash-sales-shock-price",
    "https://www.bigc.co.th/p/campaign-bug-buster-sale",
]
MAKRO_PRO_SEARCH = "https://www.makro.pro/th/c/search"
MAKRO_PROMOTION_SURFACES = [
    "https://www.makro.co.th/th/catalog",
    "https://www.makro.co.th/en/catalog",
]



GOURMET_HOME = "https://gourmetmarketthailand.com/"
GOURMET_GRAPHQL = "https://api-stark.gourmetmarketthailand.com/graphql"



def _decode_js_escapes(text):
    """Decode only safe common JS/JSON escape sequences without touching native Thai text."""
    s=str(text or '')
    s=s.replace('\\/','/').replace('\\n','\n').replace('\\r','\n').replace('\\t',' ')
    def u4(m):
        try:return chr(int(m.group(1),16))
        except Exception:return m.group(0)
    def x2(m):
        try:return chr(int(m.group(1),16))
        except Exception:return m.group(0)
    s=re.sub(r'\\u([0-9a-fA-F]{4})',u4,s)
    s=re.sub(r'\\x([0-9a-fA-F]{2})',x2,s)
    s=s.replace('\\"','"').replace("\\'", "'")
    return html_lib.unescape(s)


def _text_projections(html,base=''):
    """Return multiple text projections from HTML/Next/RSC payloads.

    Modern commerce pages can expose useful product facts either as normal DOM text
    or escaped inside React/Next flight payloads.  We keep both projections and let
    source-specific parsers apply strict product/price semantics afterward.
    """
    raw=str(html or '')
    out=[]
    if BeautifulSoup and raw:
        try:
            soup=BeautifulSoup(raw,'html.parser')
            out.append('\n'.join(_clean(x) for x in soup.get_text('\n').splitlines() if _clean(x)))
        except Exception:pass
    try:
        p=parse_page(base or '',raw)
        if p.get('text'):out.append(str(p.get('text')))
    except Exception:pass
    dec=_decode_js_escapes(raw)
    # Keep one decoded projection WITH script/Next-flight payload text. This is
    # important for modern SSR pages where visible product facts are serialized
    # in self.__next_f / hydration data even when the normal DOM is thin.
    dec_all=re.sub(r'<[^>]+>','\n',dec)
    dec_all=html_lib.unescape(dec_all)
    dec_all=re.sub(r'[ \t]+',' ',dec_all)
    dec_all=re.sub(r'\n{2,}','\n',dec_all)
    out.append(dec_all)
    # Also keep a cleaner body-only projection to reduce JavaScript noise.
    dec_body=re.sub(r'<(?:script|style)[^>]*>.*?</(?:script|style)>',' ',dec,flags=re.I|re.S)
    dec_body=re.sub(r'<[^>]+>','\n',dec_body)
    dec_body=html_lib.unescape(dec_body)
    dec_body=re.sub(r'[ \t]+',' ',dec_body)
    dec_body=re.sub(r'\n{2,}','\n',dec_body)
    out.append(dec_body)
    # Keep order while removing exact duplicates.
    uniq=[]
    for x in out:
        x=str(x or '').strip()
        if x and x not in uniq:uniq.append(x)
    return uniq


def _first_meta_content(html,*keys):
    if not BeautifulSoup or not html:return ''
    try:
        soup=BeautifulSoup(html,'html.parser')
        for k in keys:
            el=soup.find('meta',attrs={'property':k}) or soup.find('meta',attrs={'name':k})
            if el and el.get('content'):return _clean(el.get('content'))
    except Exception:pass
    return ''

def _clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def _label_clean(x):
    s=_clean(x)
    s=re.sub(r'[\]\[(){}\"\';,]+$','',s).strip()
    return s


def _money_values(text, allow_bare=False):
    text = str(text or "")
    vals = []
    for m in re.finditer(r"฿\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:บาท|THB)", text, re.I):
        raw = m.group(1) or m.group(2)
        try:
            v = float(raw.replace(",", ""))
            if 0 < v < 1000000:
                vals.append(v)
        except Exception:
            pass
    if vals or not allow_bare:
        return vals
    for raw in re.findall(r"(?<![\d.])(\d{1,6}(?:,\d{3})*(?:\.\d{2}))(?![\d.])", text):
        try:
            v = float(raw.replace(",", ""))
            if 0 < v < 1000000:
                vals.append(v)
        except Exception:
            pass
    return vals


def _dedup(rows):
    out, seen = [], set()
    for r in rows or []:
        k = (
            r.get("record_type"), r.get("sku") or r.get("source_url"),
            r.get("product_name") or r.get("promotion_title"), r.get("price")
        )
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _same_host_family(url, allowed):
    try:
        h = urlparse(url).netloc.lower()
        return any(h == x or h.endswith("." + x) for x in allowed)
    except Exception:
        return False


def _links(html, base, pattern=None):
    out = []
    if not html:
        return out
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            u = urljoin(base, a.get("href") or "")
            if pattern and not re.search(pattern, u, re.I):
                continue
            if u not in out:
                out.append(u)
        return out
    for href in re.findall(r'''href=["']([^"']+)''', html, re.I):
        u = urljoin(base, href)
        if pattern and not re.search(pattern, u, re.I):
            continue
        if u not in out:
            out.append(u)
    return out


def _sku_bigc(url):
    m = re.search(r"\.(\d+)(?:[/?#]|$)", url or "")
    return m.group(1) if m else ""


def _canonical_makro(url):
    if not url:
        return url
    p = urlparse(url)
    return urllib.parse.urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _card_container(anchor, max_up=7):
    node = anchor
    for _ in range(max_up):
        parent = getattr(node, "parent", None)
        if not parent:
            break
        tx = _clean(" ".join(parent.stripped_strings))
        node = parent
        if 20 <= len(tx) <= 1400 and ("฿" in tx or re.search(r"\d+\.\d{2}", tx)):
            return node
    return node


def _price_texts(container):
    current, regular = [], []
    if not container:
        return current, regular
    try:
        for el in container.find_all(True, limit=120):
            attrs = " ".join([
                " ".join(el.get("class") or []), str(el.get("id") or ""),
                str(el.get("data-testid") or ""), str(el.get("aria-label") or "")
            ]).lower()
            tx = _clean(" ".join(el.stripped_strings))
            if not tx:
                continue
            if any(k in attrs for k in ("price", "amount", "sale")):
                if any(k in attrs for k in ("old", "regular", "original", "compare", "before", "strike", "rrp")):
                    regular.append(tx)
                else:
                    current.append(tx)
    except Exception:
        pass
    return current, regular


def _choose_prices(container):
    current_text, regular_text = _price_texts(container)
    cur, reg = [], []
    for tx in current_text:
        cur += _money_values(tx, allow_bare=True)
    for tx in regular_text:
        reg += _money_values(tx, allow_bare=True)
    whole = _clean(" ".join(container.stripped_strings)) if container else ""
    explicit = _money_values(whole)
    if not cur and explicit:
        cur = explicit[:]
    if not cur:
        cur = _money_values(whole, allow_bare=True)
    if not cur:
        return None, None
    current = cur[0]
    regular = reg[0] if reg else None
    if regular is None:
        bigger = [v for v in explicit + cur[1:] if v > current]
        if bigger:
            regular = min(bigger)
    return current, regular


def bigc_listing_rows(html, base):
    if not BeautifulSoup or not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if "/product/" not in href:
            continue
        u = urljoin(base, href)
        if "bigc.co.th" not in urlparse(u).netloc.lower():
            continue
        name = _clean(" ".join(a.stripped_strings))
        if len(name) < 3:
            im = a.find("img")
            if im:
                name = _clean(im.get("alt") or im.get("title") or "")
        if len(name) < 3:
            continue
        current, regular = _choose_prices(_card_container(a))
        if current is None:
            continue
        rows.append({
            "record_type": "ProductCandidate", "product_name": name[:300], "brand": "",
            "category": (urlparse(base).path.split("/category/")[-1].split("/")[0] if "/category/" in urlparse(base).path else ""),
            "price": current, "regular_price": regular,
            "promo_price": current if regular is not None and current < regular else None,
            "currency": "THB", "sku": _sku_bigc(u), "source_url": u,
            "source_tag": "Product", "provenance": "bigc-category-card"
        })
    return _dedup(rows)



def _public_sitemap_urls(seed, product_pattern=None, max_sitemaps=16):
    """Read official robots/sitemap XML and return same-site URLs.

    Keeps this helper source-specific so Big C can use the sitemap as an operational
    product universe instead of treating the 12 displayed URLCandidate samples as
    the full catalog.
    """
    u=urlparse(seed);origin=f"{u.scheme or 'https'}://{u.netloc}"
    roots=[origin+'/robots.txt',origin+'/sitemap.xml',origin+'/sitemap_index.xml']
    maps=[];diag=[]
    for rurl in roots:
        r=get(rurl,timeout=12)
        if not r.get('ok'):
            diag.append({'url':rurl,'status':'failed','error':r.get('error')});continue
        txt=r.get('text') or '';diag.append({'url':rurl,'status':'fetched','bytes':r.get('bytes',0)})
        if rurl.endswith('robots.txt'):
            maps += re.findall(r'^\s*Sitemap:\s*(https?://\S+)',txt,re.I|re.M)
        else:
            maps.append(r.get('final_url') or rurl)
    q=[]
    for x in maps:
        if x not in q:q.append(x)
    seen=set();urls=[]
    while q and len(seen)<max_sitemaps:
        sm=q.pop(0)
        if sm in seen:continue
        seen.add(sm);r=get(sm,timeout=15)
        if not r.get('ok'):continue
        locs=re.findall(r'<loc>\s*(.*?)\s*</loc>',r.get('text') or '',re.I|re.S)
        for loc in locs:
            loc=loc.replace('&amp;','&').strip()
            if loc.endswith('.xml') and len(seen)+len(q)<max_sitemaps:
                if loc not in q:q.append(loc)
                continue
            if not _same_host_family(loc,[u.netloc.lower().removeprefix('www.')]):continue
            if product_pattern and not re.search(product_pattern,loc,re.I):continue
            urls.append(loc)
    return list(dict.fromkeys(urls)),list(seen),diag


def _canonical_bigc_product_url(url):
    if not url:return url
    p=urlparse(url);path=re.sub(r'^/en(?=/product/)','',p.path,flags=re.I)
    return urllib.parse.urlunparse((p.scheme,p.netloc,path,'','',''))


def _bigc_product_universe(seed,max_sitemaps=16):
    urls,maps,diag=_public_sitemap_urls(seed,r'/(?:en/)?product/',max_sitemaps=max_sitemaps)
    # Thai and English sitemap entries represent the same product. Prefer the Thai URL.
    by={}
    for u in urls:
        k=_canonical_bigc_product_url(u)
        if k not in by or '/en/product/' in by[k]:by[k]=k
    return list(by.values()),maps,diag

def _thai_date_iso(raw):
    """Normalize common Big C dd/mm/yy[yy] validity dates to ISO.

    Big C commonly publishes Buddhist-era 2-digit years (e.g. 06/09/69 =
    6 Sep 2569 BE = 2026 CE). Preserve unknown shapes as an empty string.
    """
    m=re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b',str(raw or ''))
    if not m:return ''
    d,mo,y=map(int,m.groups())
    if y<100:
        y=2500+y-543
    elif y>=2400:
        y-=543
    if not (2000<=y<=2100 and 1<=mo<=12 and 1<=d<=31):return ''
    return f'{y:04d}-{mo:02d}-{d:02d}'


def _bigc_main_segment(text,name='',sku=''):
    """Return the focal Big C product block, excluding similar-product carousels."""
    s=str(text or '')
    # The similar-products section contains many unrelated prices and must never be
    # used for the focal item. Footer markers are secondary stops.
    stops=['สินค้าใกล้เคียง','Similar Products','บิ๊กซีออนไลน์','Big C Online']
    cut=len(s)
    for marker in stops:
        i=s.find(marker)
        if i>=0:cut=min(cut,i)
    s=s[:cut]
    anchor=-1
    sid=re.escape(str(sku or ''))
    if sid:
        pats=[rf'รหัส\s*สินค้า\s*[:：#]?\s*{sid}\b',rf'\bID\s*[:：#]?\s*{sid}\b',
              rf'Product\s*(?:ID|Code)\s*[:：#]?\s*{sid}\b']
        for pat in pats:
            m=re.search(pat,s,re.I|re.S)
            if m:anchor=m.start();break
    if anchor<0 and name:
        i=s.find(name)
        if i>=0:anchor=i
    if anchor>=0:
        # Include promotional badge immediately before the title/code and all focal
        # product facts through product details, while excluding the carousel.
        return s[max(0,anchor-800):min(len(s),anchor+7000)]
    return s[:9000]


def _bigc_structured_price(decoded,sku):
    """Find price values in a JSON/Next object close to the focal product ID."""
    if not decoded or not sku:return (None,None)
    sid=re.escape(str(sku))
    anchors=[]
    for pat in [rf'"(?:id|sku|productId|product_id|productCode)"\s*:\s*"?{sid}"?',
                rf'(?:รหัส\s*สินค้า|Product\s*(?:ID|Code)|\bID)\s*[:：#]?\s*{sid}\b']:
        anchors += [m.start() for m in re.finditer(pat,decoded,re.I|re.S)]
    keys=r'(?:finalPrice|sellingPrice|salePrice|specialPrice|currentPrice|discountPrice|price)'
    regkeys=r'(?:regularPrice|originalPrice|beforePrice|compareAtPrice|rrp)'
    for a in anchors[:12]:
        seg=decoded[max(0,a-1200):a+5000]
        cur=[];reg=[]
        for m in re.finditer(rf'"{keys}"\s*:\s*"?([\d,]+(?:\.\d+)?)',seg,re.I):
            try:
                v=float(m.group(1).replace(',',''))
                if 0<v<1000000:cur.append(v)
            except Exception:pass
        for m in re.finditer(rf'"{regkeys}"\s*:\s*"?([\d,]+(?:\.\d+)?)',seg,re.I):
            try:
                v=float(m.group(1).replace(',',''))
                if 0<v<1000000:reg.append(v)
            except Exception:pass
        # Explicit currency near the focal product is stronger than an unlabelled
        # generic JSON numeric field.
        money=_money_values(seg)
        if money:
            current=money[0]
            regular=next((v for v in money[1:] if v>current),None)
            return current,regular
        if cur:
            current=cur[0]
            regular=next((v for v in reg if v>current),None)
            if regular is None:regular=next((v for v in cur[1:] if v>current),None)
            return current,regular
    return None,None


def bigc_detail_record(html, url):
    """Materialize a Big C focal product across multiple current page templates.

    Supports DOM, flattened accessible text, and escaped Next/RSC payloads. Product
    identity comes from the official product URL/SKU; price is accepted only from
    the focal product block, never from coupon text or the similar-product carousel.
    """
    if not html:return None
    sku=_sku_bigc(url);name='';brand='';category='';price=None;regular=None
    promotion_mechanic='';end_date='';parser_mode=''

    if BeautifulSoup:
        try:
            soup=BeautifulSoup(html,'html.parser')
            h=soup.find('h1')
            if h:name=_clean(' '.join(h.stripped_strings))
        except Exception:pass
    if not name:
        name=_first_meta_content(html,'og:title','twitter:title')
        name=re.sub(r'\s*-\s*Big C Online.*$','',name,flags=re.I).strip()
    if not name:
        try:
            title=_clean(parse_page(url,html).get('title') or '')
            name=re.sub(r'\s*-\s*Big C Online.*$','',title,flags=re.I).strip()
        except Exception:pass

    projections=_text_projections(html,url)
    for text in projections:
        lines=[_clean(x) for x in str(text or '').splitlines() if _clean(x)]
        joined='\n'.join(lines)

        # SKU labels vary slightly by template. The URL remains authoritative if the
        # body does not expose a code.
        for line in lines:
            m=re.search(r'(?:รหัส\s*สินค้า|Product\s*(?:ID|Code)|\bID)\s*[:：#]?\s*(\d+)',line,re.I)
            if m:sku=m.group(1);break

        # Brand/category can be compact (แบรนด์โค้ก) or split across adjacent nodes.
        for i,line in enumerate(lines):
            m=re.match(r'^(?:แบรนด์|Brand)\s*[:：]?\s*(.+)$',line,re.I)
            if m and _clean(m.group(1)):brand=_label_clean(m.group(1))[:120]
            elif re.fullmatch(r'(?:แบรนด์|Brand)\s*[:：]?',line,re.I) and i+1<len(lines):brand=_label_clean(lines[i+1])[:120]
            m=re.match(r'^(?:หมวดหมู่|Category)\s*[:：]?\s*(.+)$',line,re.I)
            if m and _clean(m.group(1)):category=_label_clean(m.group(1))[:160]
            elif re.fullmatch(r'(?:หมวดหมู่|Category)\s*[:：]?',line,re.I) and i+1<len(lines):category=_label_clean(lines[i+1])[:160]

        focal=_bigc_main_segment(joined,name,sku)
        # Selling price is the first explicit baht amount in the focal product block.
        # This supports ฿56/แพ็ค, ฿16/กระป๋อง, ฿25/ขวด, and regular-price shapes such
        # as ฿62-9%.
        vals=_money_values(focal)
        if vals and price is None:
            price=vals[0]
            regular=next((v for v in vals[1:] if v>price),None)
            parser_mode='focal-visible-text'

        if not promotion_mechanic:
            mechanics=[]
            for pat in [r'สินค้าโปรโมชัน',r'ซื้อ\s*\d+\s*ถูกลง',r'ถูกจริงประหยัดจริง',r'Flash\s*Sale',r'ราคาพิเศษ']:
                m=re.search(pat,focal,re.I)
                if m:mechanics.append(_clean(m.group(0)))
            promotion_mechanic='; '.join(dict.fromkeys(mechanics))[:300]
        if not end_date:
            m=re.search(r'(?:หมดเขต|ถึง|valid\s*(?:until|to))\s*[:：]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',focal,re.I)
            if m:end_date=_thai_date_iso(m.group(1))

        if price is not None and (brand or category):break

    # Raw/escaped Next/RSC fallback. This intentionally searches *around the focal
    # SKU*, allowing arbitrary tags/newlines between label, code and baht price.
    dec=_decode_js_escapes(html)
    if price is None and sku:
        sid=re.escape(str(sku))
        for pat in [rf'(?:รหัส\s*สินค้า|Product\s*(?:ID|Code)|\bID).{{0,800}}?{sid}.{{0,3500}}?(฿\s*[\d,.]+)',
                    rf'{sid}.{{0,2200}}?(฿\s*[\d,.]+)']:
            m=re.search(pat,dec,re.I|re.S)
            if m:
                vals=_money_values(m.group(0))
                if vals:
                    price=vals[0];regular=next((v for v in vals[1:] if v>price),None)
                    parser_mode='decoded-focal-currency';break
    if price is None:
        price,regular=_bigc_structured_price(dec,sku)
        if price is not None:parser_mode='structured-next-state'

    # Last-resort label extraction from decoded payloads.
    combined='\n'.join(projections+[dec])
    if not brand:
        m=re.search(r'(?:^|\n|[";,])\s*แบรนด์\s*[:：]?\s*([^\n";,]{2,100})',combined,re.I)
        if m:brand=_label_clean(m.group(1))[:120]
    if not category:
        m=re.search(r'(?:^|\n|[";,])\s*หมวดหมู่\s*[:：]?\s*([^\n";,]{2,140})',combined,re.I)
        if m:category=_label_clean(m.group(1))[:160]
    if not promotion_mechanic:
        m=re.search(r'(สินค้าโปรโมชัน|ซื้อ\s*\d+\s*ถูกลง|ถูกจริงประหยัดจริง|ราคาพิเศษ)',combined,re.I)
        if m:promotion_mechanic=_clean(m.group(1))
    if not end_date:
        m=re.search(r'(?:หมดเขต|ถึง|valid\s*(?:until|to))\s*[:：]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',combined,re.I)
        if m:end_date=_thai_date_iso(m.group(1))

    if not name:
        slug=urlparse(url).path.rstrip('/').split('/')[-1]
        slug=re.sub(r'\.\d+$','',slug)
        name=_clean(slug.replace('-',' '))
    if not name or price is None:return None
    return {'record_type':'ProductCandidate','product_name':name[:300],'brand':brand[:120],'category':category[:160],
            'price':price,'regular_price':regular,'promo_price':price if regular and price<regular else (price if promotion_mechanic else None),
            'promotion_mechanic':promotion_mechanic,'start_date':'','end_date':end_date,
            'currency':'THB','sku':str(sku or ''),'source_url':_canonical_bigc_product_url(url),
            'source_tag':'Product','provenance':'bigc-sitemap-product-detail','parser_mode':parser_mode}


def _bigc_categories(seed):
    if "/category/" in (seed or ""):
        return [seed]
    r = get("https://www.bigc.co.th/", timeout=15)
    cats = []
    if r.get("ok"):
        cats = [u for u in _links(r.get("text") or "", r.get("final_url") or seed, r"/category/") if "/product/" not in u]
    out = []
    for u in cats + BIGC_DEFAULT_CATEGORIES:
        u = u.split("?")[0].rstrip("/")
        if u not in out:
            out.append(u)
    return out[:18]


def bigc_product_catalog(seed, max_pages=3, source_id=None, progressive=False, operational_config=None, stable_sample=False):
    """Big C product catalog via official sitemap -> product detail.

    Explore is deliberately FAST and bounded: it samples only a few product-detail
    URLs and never launches repeated browser renders. Deep Audit/Acquire may use the
    persisted profile with a larger bounded batch.
    """
    cfg=dict(operational_config or {})
    explore_mode=not progressive
    max_sitemaps=int(cfg.get('max_sitemaps') or (10 if explore_mode else max(12,min(18,max_pages*3))))
    universe,maps,sitemap_diag=_bigc_product_universe(seed,max_sitemaps=max_sitemaps)

    requested=max(1,int(max_pages))
    target=min(2,requested) if explore_mode else requested
    run_no=0
    if progressive and source_id and universe:
        try:
            from operations_store import states
            run_no=max(0,int((states().get(source_id) or {}).get('total_runs') or 0)-1)
        except Exception:run_no=0

    offset=(run_no*target)%len(universe) if progressive and universe and not stable_sample else 0
    # Explore tries at most four direct details; operational mode has more spare URLs.
    multiplier=2 if explore_mode else 3
    window=universe[offset:offset+target*multiplier]
    if len(window)<target*multiplier and offset:
        window += universe[:target*multiplier-len(window)]

    rows=[];diag=list(sitemap_diag);checked=[];render_attempts=0
    started=time.monotonic()
    time_budget=12.0 if explore_mode else max(35.0,min(75.0,18.0+requested*8.0))
    direct_timeout=6 if explore_mode else 12
    render_cap=0 if explore_mode else min(2,max(1,target))
    render_timeout=14 if not explore_mode else 0

    for u in window:
        if len(rows)>=target:break
        if time.monotonic()-started >= time_budget:
            diag.append({'stage':'sitemap-product-detail','status':'time-budget-reached',
                         'budget_seconds':time_budget,'tested':len(checked),'materialized':len(rows)})
            break
        r=get(u,timeout=direct_timeout);checked.append(u)
        if not r.get('ok'):
            diag.append({'stage':'sitemap-product-detail','url':u,'status':'failed','error':r.get('error')});continue

        html=r.get('text') or ''
        # Explicitly expose whether the direct response is useful or just an anti-bot/shell page.
        challenge=('Just a moment...' in html or 'challenge-error-text' in html or
                   'cf-chl-' in html or 'Attention Required' in html)
        rec=None if challenge else bigc_detail_record(html,r.get('final_url') or u)
        render_status=None

        # Browser render is operational fallback only. Explore must remain responsive;
        # if direct public HTML is insufficient, diagnostics report that instead of
        # blocking the entire technique bench for 30-60 seconds.
        if not rec and not challenge and render_attempts<render_cap and (time.monotonic()-started)<time_budget-5:
            render_attempts+=1
            br=browser_render(r.get('final_url') or u,timeout=render_timeout)
            bhtml=br.get('html') or ''
            if br.get('ok') and bhtml and 'Just a moment...' not in bhtml and 'challenge-error-text' not in bhtml:
                rec=bigc_detail_record(bhtml,r.get('final_url') or u)
                render_status='materialized' if rec else 'no-product-record'
            else:
                render_status='challenge-or-failed'

        if rec:
            rows.append(rec)
            diag.append({'stage':'sitemap-product-detail','url':u,'status':'materialized',
                         'sku':rec.get('sku'),'price':rec.get('price'),'regular_price':rec.get('regular_price'),
                         'parser_mode':rec.get('parser_mode'),'promotion_mechanic':rec.get('promotion_mechanic'),
                         'end_date':rec.get('end_date'),'direct_bytes':r.get('bytes'),'rendered_fallback':render_status})
        else:
            diag.append({'stage':'sitemap-product-detail','url':u,
                         'status':'challenge-response' if challenge else 'no-product-record',
                         'direct_bytes':r.get('bytes'),'rendered_fallback':render_status})

    rows=_dedup(rows)
    tested=len(checked);success_pct=round(100*len(rows)/tested,1) if tested else 0
    price_pct=round(100*sum(x.get('price') is not None for x in rows)/len(rows),1) if rows else 0
    sku_pct=round(100*sum(bool(x.get('sku')) for x in rows)/len(rows),1) if rows else 0
    elapsed=round(time.monotonic()-started,2)
    cfg={'product_universe':'official-sitemap','max_sitemaps':max_sitemaps,
         'batch_size':requested,'explore_sample_size':2,
         'commerce_surface':'https://www.bigc.co.th/product/','official_domain':'bigc.co.th'}
    return {'rows':rows,'diagnostics':diag,'urls_checked':checked+maps,
      'potential':{'product_urls_discovered':len(universe),'product_detail_urls_tested':tested,
        'product_records':len(rows),'detail_materialization_success_pct':success_pct,
        'price_completeness_pct':price_pct,'sku_completeness_pct':sku_pct,
        'explore_fast_mode':explore_mode,'time_budget_seconds':time_budget,
        'technique_elapsed_seconds':elapsed,'render_fallback_attempts':render_attempts,
        'estimated_extractable_records_low':len(rows),'estimated_extractable_records_high':len(universe),
        'confidence':'high' if rows and success_pct>=80 and price_pct>=90 else 'medium' if rows else 'low',
        'operational_config':cfg,
        'data_fields':['product name','SKU','brand','category','current price','regular price','product URL'],
        'basis':'official Big C sitemap product universe + time-bounded public product-detail materialization'}}
def bigc_promotion_surface(max_pages=3):
    rows, diag, checked = [], [], []
    for u in BIGC_PROMOTION_SURFACES[:max(1, min(len(BIGC_PROMOTION_SURFACES), max_pages))]:
        r = get(u, timeout=15)
        checked.append(u)
        if not r.get("ok"):
            diag.append({"url": u, "status": "failed", "error": r.get("error")})
            continue
        p = parse_page(r.get("final_url") or u, r.get("text") or "")
        title = _clean(p.get("title") or "")
        if title and not re.search(r"วิธีใช้คูปอง|how to use coupon", title, re.I):
            rows.append({
                "record_type": "PromotionCandidate", "promotion_title": title[:220],
                "offer": title, "terms": "", "source_url": r.get("final_url") or u,
                "source_tag": "Marketing", "provenance": "bigc-official-campaign"
            })
        diag.append({"url": u, "status": "fetched", "title": title})
    return {
        "rows": _dedup(rows), "diagnostics": diag, "urls_checked": checked,
        "potential": {"promotion_records": len(rows), "confidence": "high" if rows else "low",
                      "basis": "official Big C campaign pages"}
    }


def _network_probe(seed, allowed_hosts, max_pages=3):
    net=browser_netlog(seed,timeout=38);diag=[];apis=[]
    if net.get('ok') or net.get('api_candidates') or net.get('all_network_urls'):
        pool=net.get('all_network_urls') or net.get('network_urls') or []
        related=[u for u in pool if _same_host_family(u,allowed_hosts)]
        # Product/search/catalog candidates only; explicitly discard telemetry noise.
        for u in related:
            if not re.search(r'/api/|graphql|catalog|product|search|listing|query|data',u,re.I):continue
            if re.search(r'/metrics/|googlead|analytics|trending-keywords|location/api/v1/stores|cookie|consent',u,re.I):continue
            if re.search(r'\.(?:jpg|jpeg|png|webp|gif|svg|ico)(?:\?|$)',u,re.I):continue
            if u not in apis:apis.append(u)
        # Preserve same-site candidates from the generic detector too.
        for u in net.get('api_candidates') or []:
            if _same_host_family(u,allowed_hosts) and u not in apis:apis.append(u)
        diag.append({'stage':'browser-network','url':seed,'status':'captured','api_candidates':len(apis),
                     'network_urls':len(net.get('network_urls') or []),'all_network_urls':len(pool),'browser':net.get('exe'),
                     'related_hosts':allowed_hosts})
    else:
        diag.append({'stage':'browser-network','url':seed,'status':'failed','error':net.get('error')})
    p=probe_json_endpoints(apis,max_endpoints=max(4,min(18,max_pages*4))) if apis else {'rows':[],'diagnostics':[],'urls_checked':[],'metrics':{}}
    diag += p.get('diagnostics') or []
    rows=[r for r in _dedup(p.get('rows') or []) if r.get('record_type') in ('ProductCandidate','PriceCandidate','PromotionCandidate')]
    return {'rows':rows,'diagnostics':diag,'urls_checked':p.get('urls_checked') or [],
            'potential':{'api_candidates':len(apis),'api_records':len(rows),
              'reported_total':(p.get('metrics') or {}).get('reported_total'),
              'confidence':'high' if rows else 'medium' if apis else 'low',
              'candidate_sample':apis[:8],
              'basis':'browser network on official/related commerce infrastructure + bounded read-only JSON probes'}}


def bigc_catalog_network(max_pages=3):
    return _network_probe("https://www.bigc.co.th/category/eggs-milk-dairy-products", ["bigc.co.th","bigc-cs.com"], max_pages)


def _makro_name_brand_from_anchor(a):
    txt = _clean(" ".join(a.stripped_strings))
    if not txt:
        return "", ""
    before = txt.split("฿", 1)[0]
    m = re.match(r"^(.*?)(\d+(?:\.\d+)?\s*(?:unit\(s\)|piece\(s\)|kg|bag\(s\)|box\(es\)|carton\(s\)|pack\(s\)|set\(s\)))(.*)$", before, re.I)
    if m:
        name, brand = _clean(m.group(1)), _clean(m.group(3))
        if name:
            return name, brand
    im = a.find("img") if hasattr(a, "find") else None
    if im:
        alt = _clean(im.get("alt") or "")
        if alt and "thumbnail" not in alt.lower() and "product-main" not in alt.lower():
            return alt, ""
    return before, ""




def _sku_makro(url):
    """Extract Makro SKU from current product routes such as /th/p/219535-6761199108291."""
    m=re.search(r'/(?:th/|en/)?p/(\d{3,})-(\d{6,})(?:[/?#]|$)',str(url or ''),re.I)
    if m:return m.group(1)
    m=re.search(r'/(?:th/|en/)?p/[^/?#]*?(\d{3,})(?:[/?#]|$)',str(url or ''),re.I)
    return m.group(1) if m else ''

def _gtin_makro(url):
    m=re.search(r'/(?:th/|en/)?p/\d{3,}-(\d{6,})(?:[/?#]|$)',str(url or ''),re.I)
    return m.group(1) if m else ''

def _makro_unit_pattern():
    # Makro PRO exposes the selling-unit separator in English even on the Thai UI
    # (e.g. 12 unit(s), 1 kg, 1 bag(s)). Avoid Thai package units here because
    # those commonly appear inside the PRODUCT NAME itself (e.g. "15 กก.").
    return r'\d+(?:\.\d+)?\s*(?:unit\(s\)|piece\(s\)|kg|bag\(s\)|box(?:es)?|carton\(s\)|pack\(s\)|set\(s\))'

def _makro_sequence_rows(text,base,urls=None):
    """Parse repeated Makro product sequences from rendered/SSR accessibility text.

    Works with both line-separated DOM text and collapsed Next/SSR text.  A sale-unit
    token (e.g. "12 unit(s)" or "1 kg") anchors each product card.
    """
    s=html_lib.unescape(_decode_js_escapes(str(text or ''))).replace('\u200b',' ')
    urls=list(urls or [])
    rows=[]

    def add(name,unit_text,tail):
        name=_clean(name);tail=_clean(tail)
        if len(name)<3 or len(name)>320:return
        parts=_makro_card_parts(f'{name} {unit_text} {tail}')
        if not parts:return
        pname,brand,current,regular=parts
        if re.search(r'รายการสินค้า|Product List|เรียงตาม|Sort By|ความใกล้เคียง|Relevance',pname,re.I):return
        u=urls[len(rows)] if len(rows)<len(urls) else base
        row={'record_type':'ProductCandidate','product_name':pname[:300],'brand':brand[:120],
             'category':'','price':current,'regular_price':regular,
             'promo_price':current if regular is not None and current<regular else None,
             'currency':'THB','sku':_sku_makro(u),'source_url':_canonical_makro(u),
             'source_tag':'Product','provenance':'makro-pro-accessible-text'}
        gtin=_gtin_makro(u)
        if gtin:row['gtin']=gtin
        rows.append(row)

    # Strong path: rendered/accessibility text normally separates title, sale unit,
    # brand and price into adjacent lines.
    lines=[_clean(x) for x in re.split(r'[\r\n]+',s) if _clean(x)]
    for i,line in enumerate(lines):
        for m in re.finditer(_makro_unit_pattern(),line,re.I):
            inline_name=_clean(line[:m.start()])
            if inline_name:
                name=inline_name
            else:
                # Previous non-UI line is the product title.
                name=''
                for j in range(i-1,max(-1,i-4),-1):
                    cand=_clean(lines[j])
                    if not cand or re.search(r'รายการสินค้า|Product List|แสดงสินค้า|Showing products|เรียงตาม|Sort By|ความใกล้เคียง|Relevance|\[Input\]',cand,re.I):
                        continue
                    name=cand;break
            tail_parts=[]
            inline_tail=_clean(line[m.end():])
            if inline_tail:tail_parts.append(inline_tail)
            if not any('฿' in x for x in tail_parts):
                for j in range(i+1,min(len(lines),i+6)):
                    nxt=_clean(lines[j])
                    # A new sale-unit token before any price means we crossed into the next card.
                    if tail_parts and re.search(_makro_unit_pattern(),nxt,re.I) and not any('฿' in x for x in tail_parts):
                        break
                    tail_parts.append(nxt)
                    if '฿' in nxt:
                        # Include one extra token only when discount/regular price is split.
                        if j+1<len(lines) and re.search(r'^฿?\s*[\d,]+(?:\.\d+)?\s*฿?(?:-\d+%)?$',_clean(lines[j+1])):
                            tail_parts.append(_clean(lines[j+1]))
                        break
            add(name,m.group(0),' '.join(tail_parts))

    # Fallback for fully collapsed text where an entire card is one long string.
    if not rows:
        flat=re.sub(r'\s+',' ',s)
        units=list(re.finditer(_makro_unit_pattern(),flat,re.I))
        prev_end=0
        headers=('รายการสินค้า','Product List','ความใกล้เคียง','Relevance','เรียงตาม','Sort By','[Input]')
        for m in units:
            prefix=flat[max(prev_end,m.start()-360):m.start()]
            for h in headers:
                pos=prefix.rfind(h)
                if pos>=0:prefix=prefix[pos+len(h):]
            # If prior item leaked into the prefix, trim after its final baht/discount token.
            cut=max(prefix.rfind('฿'),prefix.rfind('%'))
            if cut>=0:prefix=prefix[cut+1:]
            name=_clean(prefix)
            tail=flat[m.end():m.end()+150]
            before=len(rows)
            add(name,m.group(0),tail)
            if len(rows)>before:
                # Approximate next boundary after the first visible price.
                pm=re.search(r'฿\s*[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s*฿',tail)
                prev_end=m.end()+(pm.end() if pm else min(len(tail),100))
    return _dedup(rows)


def _makro_card_for_anchor(a):
    node=a;best=None
    target=_canonical_makro(urljoin('https://www.makro.pro/',a.get('href') or '')) if hasattr(a,'get') else ''
    for _ in range(14):
        tx=_clean(' '.join(getattr(node,'stripped_strings',[]) or []))
        hrefs=[]
        try:
            for x in node.find_all('a',href=True):
                h=x.get('href') or ''
                if '/p/' in h:hrefs.append(_canonical_makro(urljoin('https://www.makro.pro/',h)))
        except Exception:pass
        unique_product_links=set(hrefs)
        # Makro cards often contain separate image/title anchors for the SAME product.
        # Count unique product identities, not raw anchor elements.
        same_product=(not unique_product_links or len(unique_product_links)==1 or
                      (target and unique_product_links=={target}))
        if ('฿' in tx or re.search(r'\d[\d,]*(?:\.\d{2})?\s*฿',tx)) and same_product and len(tx)<=4200:
            best=node;break
        parent=getattr(node,'parent',None)
        if not parent:break
        node=parent
    return best or a

def _makro_card_parts(text):
    text=_clean(text)
    unit_pat=_makro_unit_pattern()
    matches=list(re.finditer(unit_pat,text,re.I))
    if not matches:return None
    m=matches[-1]
    name=_clean(text[:m.start()])
    tail=_clean(text[m.end():])
    if not name or len(name)>320:return None

    current=None;regular=None;brand=''
    # Normal form: BRAND฿49 [฿59]
    mm=re.search(r'฿\s*([\d,]+(?:\.\d+)?)',tail)
    if mm:
        before=tail[:mm.start()]
        # Discounted compact form: BRAND1,600฿1,970฿-18%
        bare=re.search(r'^(.*?)([\d,]+(?:\.\d+)?)\s*$',before)
        rest=tail[mm.end():]
        discounted_compact=bool(bare and _clean(bare.group(1)) and (re.search(r'฿\s*-?\d+%',rest) or re.search(r'-\d+%',rest)))
        if discounted_compact:
            brand=_clean(bare.group(1))
            try:current=float(bare.group(2).replace(',',''))
            except Exception:current=None
            try:regular=float(mm.group(1).replace(',',''))
            except Exception:regular=None
            if current is not None and regular is not None and regular<=current:
                current,regular=regular,None
        else:
            brand=_clean(before)
            try:current=float(mm.group(1).replace(',',''))
            except Exception:current=None
            vals=_money_values(rest)
            if vals:
                regular=next((v for v in vals if current is not None and v>current),None)
    else:
        # Compact alternate form: BRAND49฿
        mm=re.search(r'^(.*?)([\d,]+(?:\.\d+)?)\s*฿',tail)
        if not mm:return None
        brand=_clean(mm.group(1))
        try:current=float(mm.group(2).replace(',',''))
        except Exception:return None

    if current is None or current<=0 or current>=1000000 or not brand:return None
    return name,brand,current,regular

def makro_embedded_rows(html,base):
    """Conservative fallback for SSR/hydration objects containing product facts."""
    if not html:return []
    rows=[]
    # Look for compact JSON-like objects with explicit product name + numeric price.
    for m in re.finditer(r'\{[^{}]{0,2500}\}',html,re.S):
        s=m.group(0)
        if not re.search(r'"(?:name|productName|title)"\s*:',s):continue
        if not re.search(r'"(?:price|finalPrice|sellingPrice|salePrice)"\s*:',s):continue
        def sval(*keys):
            for k in keys:
                mm=re.search(r'"'+re.escape(k)+r'"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',s,re.S)
                if mm:return bytes(mm.group(1),'utf-8').decode('unicode_escape',errors='ignore')
            return ''
        def nval(*keys):
            for k in keys:
                mm=re.search(r'"'+re.escape(k)+r'"\s*:\s*"?([\d,.]+)',s)
                if mm:
                    try:return float(mm.group(1).replace(',',''))
                    except:pass
            return None
        name=_clean(sval('name','productName','title'));price=nval('price','finalPrice','sellingPrice','salePrice')
        if not name or price is None or price<=0:continue
        href=sval('url','href','productUrl','slug');u=urljoin(base,href) if href else base
        if href and '/p/' not in u:continue
        regular=nval('regularPrice','originalPrice','listPrice')
        rows.append({'record_type':'ProductCandidate','product_name':name[:300],'brand':_clean(sval('brandName','brand'))[:120],
                     'category':'','price':price,'regular_price':regular,
                     'promo_price':price if regular and price<regular else None,'currency':'THB','sku':_clean(sval('sku','productCode','code')),
                     'source_url':_canonical_makro(u),'source_tag':'Product','provenance':'makro-pro-embedded-state'})
    return _dedup(rows)


def _makro_product_urls_from_html(html,base):
    dec=_decode_js_escapes(html)
    found=[]
    # Capture normal/escaped hrefs and absolute links. Query strings are stripped
    # because product identity is stable in the /p/<slug-id> path.
    pats=[r'https?://[^"\'<>\s]+/(?:th/)?p/[^"\'<>\s?#]+',r'/(?:th/)?p/[A-Za-z0-9_-]+-\d+']
    for pat in pats:
        for m in re.finditer(pat,dec,re.I):
            u=_canonical_makro(urljoin(base,m.group(0)))
            if _same_host_family(u,['makro.pro']) and u not in found:found.append(u)
    return found


def makro_text_rows(html,base):
    """Parse Makro PRO product facts from DOM/SSR/Next accessibility text."""
    if not html:return []
    urls=_makro_product_urls_from_html(html,base)
    all_rows=[]
    for projection in _text_projections(html,base):
        # First parse repeated sequences across the whole projection. This handles
        # rendered DOM where title/unit/brand/price may be split across nodes.
        seq=_makro_sequence_rows(projection,base,urls)
        all_rows.extend(seq)
        # Keep the old line-level parser as an additional conservative path.
        lines=[_clean(x) for x in projection.splitlines() if _clean(x)]
        line_candidates=[]
        for line in lines:
            if '฿' not in line:continue
            parts=_makro_card_parts(line)
            if not parts:continue
            name,brand,price,regular=parts
            for marker in ('รายการสินค้า','Product List','ความใกล้เคียง','Relevance','เรียงตาม','Sort By'):
                if marker in name:name=_clean(name.split(marker)[-1])
            if len(name)<3 or len(name)>300:continue
            line_candidates.append((name,brand,price,regular))
        for i,(name,brand,price,regular) in enumerate(line_candidates):
            u=urls[i] if i<len(urls) else base
            row={'record_type':'ProductCandidate','product_name':name[:300],'brand':brand[:120],
                 'category':'','price':price,'regular_price':regular,
                 'promo_price':price if regular is not None and price<regular else None,
                 'currency':'THB','sku':_sku_makro(u),'source_url':_canonical_makro(u),
                 'source_tag':'Product','provenance':'makro-pro-accessible-text'}
            gtin=_gtin_makro(u)
            if gtin:row['gtin']=gtin
            all_rows.append(row)
    return _dedup(all_rows)

def makro_listing_rows(html, base):
    if not BeautifulSoup or not html:return []
    soup=BeautifulSoup(html,'html.parser');rows=[]
    for a in soup.find_all('a',href=True):
        href=a.get('href') or ''
        if '/p/' not in href:continue
        u=_canonical_makro(urljoin(base,href))
        if not _same_host_family(u,['makro.pro']):continue
        card=_makro_card_for_anchor(a);card_text=_clean(' '.join(card.stripped_strings))
        parts=_makro_card_parts(card_text)
        if not parts:
            # Some cards put all accessible text inside the anchor itself.
            parts=_makro_card_parts(_clean(' '.join(a.stripped_strings)))
        if parts:
            name,brand,current,regular=parts
        else:
            name,brand=_makro_name_brand_from_anchor(a);vals=_money_values(card_text)
            if not vals:continue
            current=vals[0];regular=next((v for v in vals[1:] if v>current),None)
        if len(name)<3:continue
        row={'record_type':'ProductCandidate','product_name':name[:300],'brand':brand[:120],
                     'category':'','price':current,'regular_price':regular,
                     'promo_price':current if regular is not None and current<regular else None,
                     'currency':'THB','sku':_sku_makro(u),'source_url':u,'source_tag':'Product','provenance':'makro-pro-listing-card'}
        gtin=_gtin_makro(u)
        if gtin:row['gtin']=gtin
        rows.append(row)
    return _dedup(rows)

def makro_detail_record(html, url):
    if not html:return None
    if BeautifulSoup:
        soup=BeautifulSoup(html,'html.parser');lines=[_clean(x) for x in soup.get_text('\n').splitlines() if _clean(x)]
        h=soup.find('h1');name=_clean(' '.join(h.stripped_strings)) if h else ''
    else:
        p=parse_page(url,html);lines=[_clean(x) for x in (p.get('text') or '').splitlines() if _clean(x)];name=_clean(p.get('title') or '')
    if not name:
        name=_first_meta_content(html,'og:title','twitter:title')
        name=re.sub(r'\s*\|\s*Makro\s*PRO\s*$','',name,flags=re.I).strip()
    brand='';sku=_sku_makro(url);price=None;regular=None;sku_idx=None
    title_idx=next((i for i,x in enumerate(lines) if name and x==name),0)
    if name and title_idx+1<len(lines):
        nxt=lines[title_idx+1]
        if 1<len(nxt)<100 and not re.search(r'฿|รหัส|code|sku|หน่วย|unit|kg',nxt,re.I):brand=nxt
    for i,line in enumerate(lines):
        if re.match(r'^(?:รหัส|Code|SKU)\s*[:：]?',line,re.I):
            m=re.search(r'(\d{3,})',line)
            if m:sku=m.group(1);sku_idx=i
        elif re.fullmatch(r'(?:รหัส|Code|SKU)',line,re.I) and i+1<len(lines):
            m=re.search(r'(\d{3,})',lines[i+1])
            if m:sku=m.group(1);sku_idx=i+1
    # Unit price can appear before the SKU. Commercial sale price appears after SKU.
    scan=lines[(sku_idx+1 if sku_idx is not None else title_idx+1):]
    vals=[];subset=scan[:18]
    for i,line in enumerate(subset):
        if line.strip()=='฿' and i+1<len(subset):
            m=re.fullmatch(r'([\d,]+(?:\.\d+)?)',subset[i+1].strip())
            if m:
                try:vals.append(float(m.group(1).replace(',','')))
                except Exception:pass
        elif '฿' in line or re.search(r'\bTHB\b|บาท',line,re.I):
            vals += _money_values(line)
        if len(vals)>=2:break
    if vals:
        price=vals[0];regular=next((v for v in vals[1:] if v>price),None)
    if not name or price is None:return None
    return {'record_type':'ProductCandidate','product_name':name[:300],'brand':brand[:120],
            'category':'','price':price,'regular_price':regular,'promo_price':price if regular and price<regular else None,
            'currency':'THB','sku':sku,'source_url':_canonical_makro(url),
            'source_tag':'Product','provenance':'makro-pro-product-detail'}

def makro_pro_catalog(seed, max_pages=3, source_id=None, progressive=False, operational_config=None, stable_sample=False):
    cfg=dict(operational_config or {});catalog=cfg.get('catalog_url') or MAKRO_PRO_SEARCH
    page_size=int(cfg.get('page_size') or 20);run_no=0
    if progressive and source_id:
        try:
            from operations_store import states
            run_no=max(0,int((states().get(source_id) or {}).get('total_runs') or 0)-1)
        except Exception:run_no=0
    page_start=run_no*max(1,max_pages)+1 if progressive and not stable_sample else 1
    rows=[];diag=[];checked=[];reported_total=None;product_urls=[]
    for n in range(page_start,page_start+max(1,int(max_pages))):
        sep='&' if '?' in catalog else '?';u=catalog if n==1 else f'{catalog}{sep}page={n}'
        r=get(u,timeout=20);checked.append(u)
        if not r.get('ok'):
            diag.append({'stage':'makro-pro-listing','url':u,'status':'failed','error':r.get('error')});continue
        html=r.get('text') or '';base=r.get('final_url') or u
        rr=makro_listing_rows(html,base)
        if not rr:rr=makro_embedded_rows(html,base)
        if not rr:rr=makro_text_rows(html,base)
        render_used=False
        # Makro PRO is server-rendered today, but headless DOM is an explicit fallback
        # if the fetched HTML contains the count but not the product-card markup.
        if not rr and n==page_start:
            br=browser_render(u,timeout=42)
            if br.get('ok') and br.get('html'):
                bhtml=br.get('html') or ''
                rr=(makro_listing_rows(bhtml,u) or
                    makro_embedded_rows(bhtml,u) or
                    makro_text_rows(bhtml,u))
                render_used=True
                burls=_makro_product_urls_from_html(bhtml,u)
                unit_tokens=len(re.findall(_makro_unit_pattern(),_decode_js_escapes(bhtml),re.I))
                price_tokens=len(re.findall(r'฿\s*[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s*฿',_decode_js_escapes(bhtml)))
                diag.append({'stage':'makro-pro-rendered-fallback','url':u,'status':'fetched','products':len(rr),
                             'browser':br.get('exe'),'dom_bytes':len(bhtml),'product_links':len(burls),
                             'unit_tokens':unit_tokens,'price_tokens':price_tokens,
                             'parser_mode':(rr[0].get('provenance') if rr else None)})
            else:
                diag.append({'stage':'makro-pro-rendered-fallback','url':u,'status':'failed','error':br.get('error') or br.get('stderr')})
        rows.extend(rr);product_urls += [x.get('source_url') for x in rr if x.get('source_url') and '/p/' in (x.get('source_url') or '')]
        parser_mode=(rr[0].get('provenance') if rr else None)
        text=_clean(parse_page(r.get('final_url') or u,html).get('text') or '')
        m=re.search(r'(?:แสดงสินค้า|showing products)\s*[\d,\s-]+\s*(?:ของ|of)\s*([\d,]+)',text,re.I)
        if m:
            try:reported_total=max(reported_total or 0,int(m.group(1).replace(',','')))
            except Exception:pass
        diag.append({'stage':'makro-pro-listing','url':u,'status':'fetched','products':len(rr),'reported_total':reported_total,'rendered_fallback':render_used,'parser_mode':parser_mode})
    rows=_dedup(rows)
    enrich={}
    for u in list(dict.fromkeys(product_urls))[:min(4,max(1,max_pages))]:
        r=get(u,timeout=18)
        if not r.get('ok'):continue
        d=makro_detail_record(r.get('text') or '',r.get('final_url') or u)
        if d:enrich[_canonical_makro(u)]=d
    for r in rows:
        d=enrich.get(_canonical_makro(r.get('source_url')))
        if d:
            for k in ('brand','sku'):
                if d.get(k):r[k]=d[k]
            # Keep the search-card price as the default single-item catalog price.
            # Product detail may show quantity-tier pricing (e.g. buy 5-11 at 47 while
            # the listing price is 49), so preserve that separately instead of
            # overwriting the listing observation.
            if d.get('price') is not None and d.get('price')!=r.get('price'):r['bulk_or_tier_price']=d.get('price')
            if d.get('regular_price') is not None and d.get('regular_price')!=r.get('price'):r['regular_price']=d.get('regular_price')
            r['promo_price']=r['price'] if r.get('regular_price') and r['price']<r['regular_price'] else None
    price_pct=round(100*sum(x.get('price') is not None for x in rows)/len(rows),1) if rows else 0
    regular_pct=round(100*sum(x.get('regular_price') is not None for x in rows)/len(rows),1) if rows else 0
    sku_pct=round(100*sum(bool(x.get('sku')) for x in rows)/len(rows),1) if rows else 0
    cfg={'catalog_url':catalog,'page_size':page_size,'pagination_param':'page','rendered_fallback':True,
         'commerce_surface':'https://www.makro.pro/','official_related_domain':'makro.pro'}
    return {'rows':rows,'diagnostics':diag,'urls_checked':checked+list(enrich),
      'potential':{'product_records':len(rows),'price_completeness_pct':price_pct,
        'regular_price_completeness_pct':regular_pct,'sku_completeness_pct':sku_pct,
        'reported_total':reported_total,'estimated_extractable_records_high':reported_total,
        'confidence':'high' if len(rows)>=15 and price_pct>=90 else 'medium' if rows else 'low',
        'operational_config':cfg,
        'data_fields':['product name','SKU','brand','current price','regular price','product URL'],
        'basis':'official Makro PRO DOM/SSR/embedded/accessibility text listing + headless rendered fallback + bounded product-detail enrichment'}}

def makro_promotion_catalogue(max_pages=2):
    rows, diag, checked = [], [], []
    reported = None
    for u in MAKRO_PROMOTION_SURFACES[:max(1, min(len(MAKRO_PROMOTION_SURFACES), max_pages))]:
        r = get(u, timeout=16)
        checked.append(u)
        if not r.get("ok"):
            diag.append({"url": u, "status": "failed", "error": r.get("error")})
            continue
        p = parse_page(r.get("final_url") or u, r.get("text") or "")
        title = _clean(p.get("title") or "Makro Promotions Catalogue")
        text = _clean(p.get("text") or "")
        m = re.search(r"(?:nearly|ประมาณ|กว่า)\s*([\d,]+)\s*(?:products|สินค้า)", text, re.I)
        if m:
            try:
                reported = int(m.group(1).replace(",", ""))
            except Exception:
                pass
        rows.append({
            "record_type": "PromotionCandidate", "promotion_title": title[:220],
            "offer": "Makro official promotions catalogue", "terms": "",
            "source_url": r.get("final_url") or u, "source_tag": "Marketing",
            "provenance": "makro-official-catalogue"
        })
        diag.append({"url": u, "status": "fetched", "reported_products": reported})
    return {
        "rows": _dedup(rows), "diagnostics": diag, "urls_checked": checked,
        "potential": {"promotion_records": len(rows), "reported_products": reported,
                      "confidence": "high" if rows else "low",
                      "basis": "official Makro promotions catalogue"}
    }


def makro_pro_network(max_pages=3):
    return _network_probe(MAKRO_PRO_SEARCH, ["makro.pro", "siammakro.cloud"], max_pages)


# ---------------------------------------------------------------------------
# Tops Online — generalized supermarket patterns learned from Lotus/Big C/Makro
# ---------------------------------------------------------------------------
TOPS_HOME = "https://www.tops.co.th/th"
TOPS_CAMPAIGN_SEEDS = [
    "https://www.tops.co.th/th/campaign/promotions/fresh-food-bakery",
    "https://www.tops.co.th/th/campaign/promotion-only-at-tops/beverages/bottled-water/drinking-water",
    "https://www.tops.co.th/th/campaign/promotion-tops-prime-jul-2026/household-and-pet",
]


def _tops_sku(url):
    """Tops detail URLs normally end with the 13-digit GTIN/SKU."""
    m=re.search(r'-(\d{8,14})(?:[/?#]|$)',str(url or ''))
    return m.group(1) if m else ''


def _canonical_tops_product_url(url):
    if not url:return url
    p=urlparse(url)
    # Tops product sitemaps occasionally contain escaped leading spaces (/%20-...).
    # Decode path escapes, remove accidental whitespace/hyphen prefixes, and normalize EN->TH.
    path=urllib.parse.unquote(p.path or '')
    path=re.sub(r'^/en(?=/)','/th',path,flags=re.I)
    path=re.sub(r'^/(th|en)/\s*-+',r'/\1/',path,flags=re.I)
    path=re.sub(r'/{2,}','/',path)
    return urllib.parse.urlunparse((p.scheme,p.netloc,path,'','',''))


def _tops_is_product_url(url):
    p=urlparse(url)
    path=p.path.lower()
    if not re.search(r'/(?:th|en)/',path):return False
    if re.search(r'/(?:campaign|page|brands-for-you|concept-store|search|category)/',path):return False
    return bool(_tops_sku(url))


def _tops_product_universe(seed,max_sitemaps=16):
    """Read official Tops product sitemap files, not the generic category/campaign universe."""
    u=urlparse(seed or TOPS_HOME);origin=f'{u.scheme or "https"}://{u.netloc or "www.tops.co.th"}'
    roots=[origin+'/robots.txt',origin+'/sitemap-index.xml']
    diag=[];maps=[]
    for ru in roots:
        r=get(ru,timeout=10)
        if not r.get('ok'):
            diag.append({'url':ru,'status':'failed','error':r.get('error')});continue
        txt=r.get('text') or ''
        diag.append({'url':ru,'status':'fetched','bytes':r.get('bytes',0)})
        if ru.endswith('robots.txt'):
            maps += re.findall(r'^\s*Sitemap:\s*(https?://\S+)',txt,re.I|re.M)
        else:
            maps.append(r.get('final_url') or ru)
            maps += re.findall(r'<loc>\s*(.*?)\s*</loc>',txt,re.I|re.S)
    q=[]
    for m in maps:
        m=html_lib.unescape(str(m or '')).strip()
        if m and m not in q:q.append(m)
    seen=[];products=[]
    while q and len(seen)<max_sitemaps:
        m=q.pop(0)
        if m in seen:continue
        # Prefer product sitemap shards. Index files are still traversed.
        if m.endswith('.xml') and ('product' not in m.lower()) and ('index' not in m.lower()):
            continue
        seen.append(m)
        r=get(m,timeout=12)
        if not r.get('ok'):continue
        locs=re.findall(r'<loc>\s*(.*?)\s*</loc>',r.get('text') or '',re.I|re.S)
        for loc in locs:
            loc=html_lib.unescape(loc).strip()
            if loc.endswith('.xml'):
                if ('product' in loc.lower() or 'index' in loc.lower()) and loc not in q and len(seen)+len(q)<max_sitemaps:q.append(loc)
                continue
            if _tops_is_product_url(loc):products.append(_canonical_tops_product_url(loc))
    # Dedup Thai/English and repeated sitemap shards by SKU.
    by={}
    for x in products:
        sku=_tops_sku(x)
        if sku and sku not in by:by[sku]=x
    return list(by.values()),seen,diag


def _tops_price_pair(text):
    """Parse Tops current/original price around the focal product block."""
    s=_clean(text)
    vals=[]
    # Explicit baht signs are strongest, especially campaign listing cards.
    vals += _money_values(s)
    # Detail pages often expose `48 / แพค` without a baht sign in accessible text.
    for m in re.finditer(r'(?<![\d.])([1-9]\d{0,5}(?:\.\d{1,2})?)\s*/\s*(?:แพค|ชิ้น|ขวด|กล่อง|กระป๋อง|ถุง|กก\.?|kg|pcs?\.?|pack|can|box|bottle)',s,re.I):
        try:
            v=float(m.group(1));
            if 0<v<1000000:vals.append(v)
        except Exception:pass
    if not vals:return None,None
    cur=vals[0]
    regular=None
    # `฿119 /ชิ้น฿169 ประหยัด ฿50` or `ปกติ ฿239`.
    m=re.search(r'(?:ปกติ|ราคาปกติ|regular|was)\s*฿?\s*([\d,]+(?:\.\d+)?)',s,re.I)
    if m:
        try:regular=float(m.group(1).replace(',',''))
        except Exception:regular=None
    if regular is None:
        bigger=[v for v in vals[1:] if v>cur]
        if bigger:regular=min(bigger)
    return cur,regular


def tops_detail_record(html,url):
    projections=_text_projections(html,url)
    if not projections:return None
    name='';sku=_tops_sku(url);price=regular=None;promo='';end_date='';parser_mode='text'
    # Meta/H1 are reliable for product identity.
    if BeautifulSoup:
        try:
            soup=BeautifulSoup(html,'html.parser')
            h=soup.find('h1')
            if h:name=_clean(' '.join(h.stripped_strings))
        except Exception:pass
    if not name:
        name=_first_meta_content(html,'og:title','twitter:title')
        name=re.sub(r'\s*\|.*$','',name).strip()
    combined='\n'.join(projections)
    if not sku:
        m=re.search(r'\bSKU\s*[:#]?\s*(\d{8,14})\b',combined,re.I)
        if m:sku=m.group(1)
    # Keep focal product text before product description/footer noise.
    seg=combined
    for marker in ('รายละเอียดสินค้า','Product Details','ต้องการความช่วยเหลือ','Need help?'):
        i=seg.find(marker)
        if i>0:seg=seg[:i]
    price,regular=_tops_price_pair(seg)
    # Promotions on detail pages: buy-X / save / validity.
    for pat in (r'(ซื้อ\s*\d+[^\n]{0,100}(?:เซฟ|ราคา)[^\n]{0,80})',r'(ซื้อ\s*\d+\s*จ่าย\s*\d+)',r'(Tops Prime Only)'):
        m=re.search(pat,seg,re.I)
        if m:promo=_clean(m.group(1));break
    m=re.search(r'(?:วันนี้\s*-|ถึง|เฉพาะวันสั่งซื้อ\s*[:：]?).{0,15}(\d{1,2}\s*(?:ม\.?ค\.?|ก\.?พ\.?|มี\.?ค\.?|เม\.?ย\.?|พ\.?ค\.?|มิ\.?ย\.?|ก\.?ค\.?|ส\.?ค\.?|ก\.?ย\.?|ต\.?ค\.?|พ\.?ย\.?|ธ\.?ค\.?)\s*\d{2,4}|\d{1,2}/\d{1,2}/\d{2,4})',seg,re.I)
    if m:end_date=_clean(m.group(1))
    if not name:
        slug=urlparse(url).path.rstrip('/').split('/')[-1]
        slug=re.sub(r'-\d{8,14}$','',slug)
        name=_clean(slug.replace('-',' '))
    if not name or not sku or price is None:return None
    return {'record_type':'ProductCandidate','product_name':name[:300],'brand':'','category':'',
            'price':price,'regular_price':regular,'promo_price':price if regular and price<regular else None,
            'promotion_mechanic':promo,'start_date':'','end_date':end_date,'currency':'THB','sku':sku,
            'source_url':_canonical_tops_product_url(url),'source_tag':'Product','provenance':'tops-sitemap-product-detail','parser_mode':parser_mode}


def tops_product_catalog(seed,max_pages=3,source_id=None,progressive=False,operational_config=None,stable_sample=False):
    """Big-C pattern generalized to Tops: official product sitemap -> detail materialization."""
    cfg=dict(operational_config or {})
    universe,maps,diag=_tops_product_universe(seed,max_sitemaps=int(cfg.get('max_sitemaps') or 16))
    requested=max(1,int(max_pages));target=min(3,requested) if not progressive else requested
    run_no=0
    if progressive and source_id and universe:
        try:
            from operations_store import states
            run_no=max(0,int((states().get(source_id) or {}).get('total_runs') or 0)-1)
        except Exception:run_no=0
    offset=(run_no*target)%len(universe) if progressive and universe and not stable_sample else 0
    window=universe[offset:offset+target*3]
    if len(window)<target*3 and offset:window += universe[:target*3-len(window)]
    rows=[];checked=[];started=time.monotonic();budget=18 if not progressive else max(40,min(80,20+requested*8))
    for u in window:
        if len(rows)>=target or time.monotonic()-started>=budget:break
        r=get(u,timeout=8 if not progressive else 12);checked.append(u)
        if not r.get('ok'):
            diag.append({'stage':'tops-product-detail','url':u,'status':'failed','error':r.get('error')});continue
        rec=tops_detail_record(r.get('text') or '',r.get('final_url') or u)
        if rec:
            rows.append(rec);diag.append({'stage':'tops-product-detail','url':u,'status':'materialized','sku':rec.get('sku'),'price':rec.get('price'),'regular_price':rec.get('regular_price')})
        else:
            diag.append({'stage':'tops-product-detail','url':u,'status':'no-product-record','bytes':r.get('bytes')})
    rows=_dedup(rows);tested=len(checked)
    price_pct=round(100*sum(r.get('price') is not None for r in rows)/len(rows),1) if rows else 0
    sku_pct=round(100*sum(bool(r.get('sku')) for r in rows)/len(rows),1) if rows else 0
    success=round(100*len(rows)/tested,1) if tested else 0
    op={'product_universe':'official-product-sitemaps','max_sitemaps':int(cfg.get('max_sitemaps') or 16),'batch_size':requested,
        'commerce_surface':'https://www.tops.co.th/th/','official_domain':'tops.co.th'}
    return {'rows':rows,'diagnostics':diag,'urls_checked':checked+maps,
      'potential':{'product_urls_discovered':len(universe),'product_detail_urls_tested':tested,'product_records':len(rows),
        'detail_materialization_success_pct':success,'price_completeness_pct':price_pct,'sku_completeness_pct':sku_pct,
        'estimated_extractable_records_high':len(universe),'confidence':'high' if rows and price_pct>=90 else 'medium' if rows else 'low',
        'operational_config':op,'data_fields':['product name','SKU','current price','regular price','promotion mechanic','product URL'],
        'basis':'official Tops product sitemap shards + public product-detail materialization'}}


def _tops_campaign_links(max_pages=4):
    r=get(TOPS_HOME,timeout=12);links=[]
    if r.get('ok'):
        links=[u.split('#')[0] for u in _links(r.get('text') or '',r.get('final_url') or TOPS_HOME,r'/th/campaign/')]
    out=[]
    for u in links+TOPS_CAMPAIGN_SEEDS:
        if u not in out:out.append(u)
    # Prefer leaf/category campaign pages because they actually expose product cards.
    out.sort(key=lambda u:(0 if len(urlparse(u).path.strip('/').split('/'))>=4 else 1,len(u)))
    return out[:max(3,max_pages*2)]


def tops_campaign_catalog(max_pages=3):
    """Makro-style listing materializer generalized to Tops campaign pages."""
    rows=[];diag=[];checked=[]
    pages=_tops_campaign_links(max_pages)
    for u in pages[:max(1,max_pages)]:
        r=get(u,timeout=12);checked.append(u)
        if not r.get('ok'):
            diag.append({'stage':'tops-campaign-listing','url':u,'status':'failed','error':r.get('error')});continue
        html=r.get('text') or '';found=[]
        if BeautifulSoup:
            try:
                soup=BeautifulSoup(html,'html.parser')
                anchors=[a for a in soup.find_all('a',href=True) if _tops_is_product_url(urljoin(r.get('final_url') or u,a.get('href') or ''))]
                seen=set()
                for a in anchors:
                    pu=_canonical_tops_product_url(urljoin(r.get('final_url') or u,a.get('href') or ''));sku=_tops_sku(pu)
                    if not sku or sku in seen:continue
                    seen.add(sku);card=_card_container(a,max_up=8);txt=_clean(' '.join(card.stripped_strings))
                    price,regular=_tops_price_pair(txt)
                    if price is None:continue
                    name=_clean(' '.join(a.stripped_strings))
                    if len(name)<3:
                        # Choose the longest non-price text fragment in the card.
                        chunks=[_clean(x) for x in card.stripped_strings if _clean(x)]
                        chunks=[x for x in chunks if '฿' not in x and not re.fullmatch(r'เพิ่ม|Add|ขายดี|Best Seller',x,re.I)]
                        if chunks:name=max(chunks,key=len)
                    if not name or re.search(r'สมัคร|ช็อปครั้ง|ส่งฟรี|ลดทันที',name):continue
                    mech=''
                    mm=re.search(r'(ซื้อ\s*\d+[^฿\n]{0,100}(?:ราคา|จ่าย|เซฟ)[^฿\n]{0,80})',txt,re.I)
                    if mm:mech=_clean(mm.group(1))
                    found.append({'record_type':'ProductCandidate','product_name':name[:300],'brand':'','category':'',
                        'price':price,'regular_price':regular,'promo_price':price if regular and price<regular else None,
                        'promotion_mechanic':mech,'currency':'THB','sku':sku,'source_url':pu,'source_tag':'Product',
                        'provenance':'tops-campaign-product-card'})
            except Exception as e:
                diag.append({'stage':'tops-campaign-listing','url':u,'status':'parse-error','error':f'{type(e).__name__}: {e}'})
        rows.extend(found)
        diag.append({'stage':'tops-campaign-listing','url':u,'status':'fetched','products':len(found),'bytes':r.get('bytes')})
    rows=_dedup(rows)
    price_pct=round(100*sum(r.get('price') is not None for r in rows)/len(rows),1) if rows else 0
    return {'rows':rows,'diagnostics':diag,'urls_checked':checked,
      'potential':{'product_records':len(rows),'price_completeness_pct':price_pct,'campaign_pages_tested':len(checked),
        'confidence':'high' if rows and price_pct>=90 else 'medium' if rows else 'low',
        'operational_config':{'campaign_seed':'homepage-discovered','commerce_surface':'https://www.tops.co.th/th/campaign/','official_domain':'tops.co.th'},
        'data_fields':['product name','SKU','current price','regular price','promotion mechanic','product URL'],
        'basis':'official Tops campaign listing cards + product identity from canonical product links'}}


def _tops_thai_range(text):
    months={'ม.ค.':1,'ก.พ.':2,'มี.ค.':3,'เม.ย.':4,'พ.ค.':5,'มิ.ย.':6,'ก.ค.':7,'ส.ค.':8,'ก.ย.':9,'ต.ค.':10,'พ.ย.':11,'ธ.ค.':12}
    month_pat=r'(?:ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)'
    m=re.search(r'(\d{1,2})\s*('+month_pat+r')\s*(\d{2,4})\s*-\s*(\d{1,2})\s*('+month_pat+r')\s*(\d{2,4})',str(text or ''))
    if not m:return '',''
    def iso(d,mon,y):
        y=int(y);y=(2500+y if y<100 else y);y=y-543 if y>=2400 else y
        mo=months.get(mon,0)
        return f'{y:04d}-{mo:02d}-{int(d):02d}' if mo else ''
    return iso(m.group(1),m.group(2),m.group(3)),iso(m.group(4),m.group(5),m.group(6))


def _tops_get_resilient(url,timeout=12):
    """Bounded retry for ordinary public Tops pages; no challenge/authentication bypass."""
    attempts=[]
    for n in range(2):
        r=get(url,timeout=timeout,headers={'Referer':TOPS_HOME,'Cache-Control':'no-cache'} if n else None)
        attempts.append(r)
        if r.get('ok'):return r,attempts
        if int(r.get('status') or 0) not in (403,429):break
        time.sleep(0.35)
    return attempts[-1] if attempts else {'ok':False,'error':'no-attempt'},attempts


def _tops_campaign_sitemap_urls(limit=20):
    """Read official campaign sitemap as a fallback when homepage requests are transiently blocked."""
    out=[]
    for sm in ('https://www.tops.co.th/sitemap/sitemap.th-campaigns.xml',
               'https://www.tops.co.th/sitemap/sitemap.en-campaigns.xml'):
        r=get(sm,timeout=10)
        if not r.get('ok'):continue
        for loc in re.findall(r'<loc>\s*(.*?)\s*</loc>',r.get('text') or '',re.I|re.S):
            u=html_lib.unescape(loc).strip()
            if '/campaign/' in u and u not in out:out.append(u)
            if len(out)>=limit:return out
    return out


def _tops_promotion_rows_from_html(html,url):
    p=parse_page(url,html or '')
    text=str(p.get('text') or '')
    lines=[_clean(x) for x in text.splitlines() if _clean(x)]
    rows=[]
    nav={'ดูทั้งหมด','View All','เพิ่ม','Add','โปรโมชั่น','Promotions','TOPS ONLINE ช็อปของเข้าบ้าน ส่งฟรี ส่งไว รับประกันความสด'}
    # Primary evidence: compact campaign block ending in a source-stated order-date range.
    for i,line in enumerate(lines):
        if not re.search(r'(?:เฉพาะวันสั่งซื้อ|วันสั่งซื้อ)\s*[:：]?',line,re.I):continue
        start,end=_tops_thai_range(line)
        prev=[x for x in lines[max(0,i-5):i] if x not in nav and not re.fullmatch(r'[-–—|]+',x)]
        if not prev:continue
        offer=next((x for x in reversed(prev) if re.search(r'฿|ลด|ซื้อ|แถม|แพค|จ่าย|สูงสุด|ครบ',x,re.I)),prev[-1])
        title=next((x for x in reversed(prev) if x!=offer and not re.search(r'^เฉพาะวัน',x)),offer)
        if re.search(r'สมัคร\s*Tops Prime|ช็อปครั้งแรก|ส่งฟรี',title+' '+offer,re.I):continue
        rows.append({'record_type':'PromotionCandidate','promotion_title':title[:220],'offer':offer[:300],'terms':line[:300],
                     'start_date':start,'end_date':end,'source_url':url,'source_tag':'Marketing','provenance':'tops-official-campaign'})
    if rows:return _dedup(rows)

    # Secondary evidence for leaf campaign pages that do not repeat the date in readable text.
    path=urlparse(url).path.lower()
    if '/campaign/' in path:
        title=''
        if BeautifulSoup:
            try:
                soup=BeautifulSoup(html or '','html.parser')
                h=soup.find('h1')
                if h:title=_clean(' '.join(h.stripped_strings))
            except Exception:pass
        if not title:title=re.sub(r'\s*\|.*$','',_first_meta_content(html,'og:title','twitter:title')).strip()
        if not title:title=_clean(p.get('title') or '')
        offer=next((x for x in lines if re.search(r'฿|ลด|ซื้อ\s*\d+|แถม|ประหยัด|โปรโมชั่น|promotion',x,re.I) and len(x)<300),'')
        if title and offer and not re.search(r'สมัคร\s*Tops Prime|ช็อปครั้งแรก|ส่งฟรี',title+' '+offer,re.I):
            rows.append({'record_type':'PromotionCandidate','promotion_title':title[:220],'offer':offer[:300],'terms':'',
                         'start_date':'','end_date':'','source_url':url,'source_tag':'Marketing','provenance':'tops-official-campaign'})
    return _dedup(rows)


def tops_promotion_surface(max_pages=4):
    """Official Tops promotion materializer with campaign-sitemap fallback.

    The generic crawler may see promotion-like text, but this technique only emits
    PromotionCandidate rows from official homepage/campaign surfaces and preserves
    source-stated date ranges when available.
    """
    rows=[];diag=[];checked=[]
    sources=[TOPS_HOME]
    for u in TOPS_CAMPAIGN_SEEDS+_tops_campaign_sitemap_urls(limit=max(8,max_pages*4)):
        if u not in sources:sources.append(u)
    # A small bounded surface set is enough for Explore; Audit can ask for more pages.
    for u in sources[:max(2,min(len(sources),max(2,int(max_pages))))]:
        r,attempts=_tops_get_resilient(u,timeout=12);checked.append(u)
        if not r.get('ok'):
            diag.append({'url':u,'status':'failed','error':r.get('error'),'attempts':len(attempts)});continue
        found=_tops_promotion_rows_from_html(r.get('text') or '',r.get('final_url') or u)
        rows.extend(found)
        diag.append({'url':u,'status':'fetched','promotion_blocks':len(found),'attempts':len(attempts),'bytes':r.get('bytes')})
    rows=_dedup(rows)
    validity=round(100*sum(bool(r.get('start_date') or r.get('end_date')) for r in rows)/len(rows),1) if rows else 0
    return {'rows':rows,'diagnostics':diag,'urls_checked':checked,
      'potential':{'promotion_records':len(rows),'validity_completeness_pct':validity,
        'confidence':'high' if rows and validity>=60 else 'medium' if rows else 'low',
        'basis':'official Tops homepage/campaign pages with campaign-sitemap fallback and source-stated order dates'}}

def tops_catalog_network(max_pages=3):
    """Lotus-style API discovery, adapted to Tops public application infrastructure."""
    # Browser rendering may be Cloudflare-blocked; bundle mining remains useful because
    # Tops publicly exposes api.tops.co.th/cms-api.tops.co.th in delivered Next assets.
    try:
        from lotus_advanced import script_bundle_mining
        x=script_bundle_mining(TOPS_HOME,max_scripts=max(8,min(18,max_pages*4)))
    except Exception as e:
        return {'rows':[],'diagnostics':[{'stage':'tops-app-bundle','status':'failed','error':f'{type(e).__name__}: {e}'}],'urls_checked':[],
                'potential':{'api_candidates':0,'confidence':'low','basis':'public Tops Next.js application bundles'}}
    cand=[]
    for u in (x.get('api_candidates') or [])+(x.get('candidate_urls') or []):
        if not re.search(r'(?:api\.tops\.co\.th|cms-api\.tops\.co\.th|tops\.co\.th/api/)',u,re.I):continue
        if not re.search(r'product|catalog|search|campaign|promotion|category|api/v2',u,re.I):continue
        if re.search(r'auth|consent|address|callback',u,re.I):continue
        if u not in cand:cand.append(u)
    # Only safe public GET probes; 405 is retained as useful evidence that an endpoint exists but expects another method.
    p=probe_json_endpoints(cand,max_endpoints=max(4,min(12,max_pages*3))) if cand else {'rows':[],'diagnostics':[],'urls_checked':[],'metrics':{}}
    rows=[r for r in _dedup(p.get('rows') or []) if r.get('record_type') in {'ProductCandidate','PriceCandidate'}]
    return {'rows':rows,'diagnostics':(x.get('diagnostics') or [])+(p.get('diagnostics') or []),'urls_checked':p.get('urls_checked') or cand[:12],
      'potential':{'api_candidates':len(cand),'api_records':len(rows),'reported_total':(p.get('metrics') or {}).get('reported_total'),
        'confidence':'high' if rows else 'medium' if cand else 'low','candidate_sample':cand[:12],
        'basis':'public Tops Next.js application bundles + bounded read-only API probes'}}


# ---------------------------------------------------------------------------
# Gourmet Market — source-specific commerce acquisition
# ---------------------------------------------------------------------------

def _gourmet_post_json(url,payload,timeout=14):
    data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    headers={
      'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36',
      'Accept':'application/json','Content-Type':'application/json',
      'Origin':'https://gourmetmarketthailand.com','Referer':GOURMET_HOME,
      'Accept-Language':'th-TH,th;q=0.9,en;q=0.7'}
    try:
        req=urllib.request.Request(url,data=data,headers=headers,method='POST')
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read(4_000_000);enc=r.headers.get_content_charset() or 'utf-8'
            txt=raw.decode(enc,'replace');ct=r.headers.get('Content-Type','')
            try:obj=json.loads(txt)
            except Exception:obj=None
            return {'ok':True,'status':getattr(r,'status',200),'content_type':ct,'text':txt,'json':obj,'bytes':len(raw)}
    except Exception as e:
        return {'ok':False,'status':getattr(e,'code',0) or 0,'error':f'{type(e).__name__}: {e}'}

def _gourmet_unwrap_image(src):
    u=html_lib.unescape(str(src or '')).replace('&quot','').strip()
    try:
        q=urllib.parse.parse_qs(urlparse(u).query)
        if '/_next/image' in u and q.get('url'):u=urllib.parse.unquote(q['url'][0])
    except Exception:pass
    return u

def _gourmet_gtin_from_image(src):
    u=_gourmet_unwrap_image(src)
    m=re.search(r'/products/(?:thumbnail|cover)/(\d{8,14})(?:[-_.]|$)',u,re.I)
    return (m.group(1),u) if m else ('',u)

def _gourmet_product_url_from_card(card,base,gtin=''):
    if card is not None and hasattr(card,'find_all'):
        anchors=[]
        if getattr(card,'name',None)=='a' and card.get('href'):anchors.append(card)
        anchors.extend(card.find_all('a',href=True))
        for a in anchors:
            href=str(a.get('href') or '')
            u=urljoin(base,href)
            if 'gourmetmarketthailand.com' not in urlparse(u).netloc.lower():continue
            if gtin and gtin in u:return u.split('#')[0]
            if re.search(r'/(?:product|products|p)/',urlparse(u).path,re.I):return u.split('#')[0]
    return base

def _gourmet_price_pair(text,raw=''):
    vals=_money_values(text)
    def field(names):
        for name in names:
            m=re.search(r"(?i)[\"']?"+re.escape(name)+r"[\"']?\s*[:=]\s*[\"']?([0-9][0-9,]*(?:\.[0-9]+)?)",raw or '')
            if m:
                try:return float(m.group(1).replace(',',''))
                except Exception:pass
        return None
    current=field(('finalPrice','sellingPrice','salePrice','specialPrice','currentPrice','price'))
    regular=field(('regularPrice','originalPrice','normalPrice','listPrice'))
    if current is None and vals:current=vals[0]
    if regular is None and current is not None:
        higher=[v for v in vals[1:] if v>current]
        if higher:regular=max(higher)
    return current,regular

def _gourmet_product_rows_from_rendered(html,base=GOURMET_HOME):
    rows=[];diag={'product_images':0,'gtin_images':0,'cards_with_price':0,'product_links':0}
    if not BeautifulSoup or not html:return rows,diag
    soup=BeautifulSoup(html,'html.parser')
    seen=set();raw=str(html)
    for img in soup.find_all('img'):
        src=img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
        image_probe=_gourmet_unwrap_image(src)
        if '/products/' not in image_probe:continue
        diag['product_images']+=1
        gtin,image_url=_gourmet_gtin_from_image(src)
        if not gtin:continue
        diag['gtin_images']+=1
        if gtin in seen:continue
        name=_clean(img.get('alt') or img.get('title') or '')
        bad=not name or len(name)<3 or re.search(r'^(?:undefined|image|product|search button|arrow-right|back to main menu)$',name,re.I)
        card=img
        chosen=None;card_text=''
        for _ in range(9):
            card=getattr(card,'parent',None)
            if card is None or not hasattr(card,'get_text'):break
            txt=_clean(card.get_text(' ',strip=True))
            if len(txt)>1400:break
            if '฿' in txt or re.search(r'\b(?:บาท|THB)\b',txt,re.I):
                chosen=card;card_text=txt;break
        if chosen is None:
            chosen=getattr(img,'parent',None);card_text=_clean(chosen.get_text(' ',strip=True)) if chosen is not None and hasattr(chosen,'get_text') else ''
        # The rendered page can keep price data in React attributes/JSON adjacent to the image.
        pos=raw.find(gtin);window=raw[max(0,pos-3500):pos+4500] if pos>=0 else ''
        price,regular=_gourmet_price_pair(card_text,window)
        if price is None:continue
        diag['cards_with_price']+=1
        if bad:
            chunks=[]
            if chosen is not None and hasattr(chosen,'stripped_strings'):
                for x in chosen.stripped_strings:
                    x=_clean(x)
                    if not x or '฿' in x or re.fullmatch(r'[0-9,.]+',x):continue
                    if re.search(r'เพิ่มสินค้า|จำนวน|รวม|add to cart|search button|arrow-right',x,re.I):continue
                    chunks.append(x)
            if chunks:name=max(chunks,key=len)[:260]
        if not name or re.search(r'^(?:ผักและผลไม้|เนื้อสัตว์|อาหารทะเล|อาหารแช่แข็ง|ของแห้ง|เครื่องดื่ม|แม่และเด็ก|สุขภาพ|ของใช้ในบ้าน)$',name,re.I):continue
        pu=_gourmet_product_url_from_card(chosen,base,gtin)
        if pu!=base:diag['product_links']+=1
        seen.add(gtin)
        rows.append({'record_type':'ProductCandidate','product_name':name[:300],'brand':'','category':'',
          'price':price,'regular_price':regular,'promo_price':price if regular and price<regular else None,
          'currency':'THB','sku':gtin,'image_url':image_url,'source_url':pu,'source_tag':'Product',
          'provenance':'gourmet-rendered-product-card','parser_mode':'rendered-card'})
    return _dedup(rows),diag

def _gourmet_scalar_price(obj,keys):
    for k in keys:
        if k not in obj:continue
        v=obj.get(k)
        if isinstance(v,dict):v=v.get('value') if v.get('value') is not None else v.get('amount')
        try:
            if v is not None and str(v).strip()!='':return float(str(v).replace(',','').replace('฿','').strip())
        except Exception:pass
    return None

def _gourmet_graphql_rows(obj,source_url=GOURMET_GRAPHQL):
    rows=[]
    def walk(x):
        if isinstance(x,dict):
            name=_clean(x.get('productName') or x.get('name') or x.get('displayName') or x.get('title') or '')
            sku=str(x.get('sku') or x.get('barcode') or x.get('ean') or x.get('gtin') or x.get('productCode') or '').strip()
            price=_gourmet_scalar_price(x,('finalPrice','sellingPrice','salePrice','specialPrice','currentPrice','price'))
            regular=_gourmet_scalar_price(x,('regularPrice','originalPrice','normalPrice','listPrice'))
            slug=_clean(x.get('slug') or x.get('urlKey') or '')
            url=_clean(x.get('productUrl') or x.get('url') or '')
            if url and not url.startswith('http'):url=urljoin(GOURMET_HOME,url)
            if not url and slug:url=urljoin(GOURMET_HOME,slug.lstrip('/'))
            if name and price is not None and (sku or url):
                brand=x.get('brand') or x.get('brandName') or ''
                if isinstance(brand,dict):brand=brand.get('name') or brand.get('title') or ''
                category=x.get('category') or x.get('categoryName') or ''
                if isinstance(category,dict):category=category.get('name') or category.get('title') or ''
                image=x.get('image') or x.get('imageUrl') or x.get('thumbnail') or ''
                if isinstance(image,dict):image=image.get('url') or image.get('src') or ''
                rows.append({'record_type':'ProductCandidate','product_name':name[:300],'brand':_clean(brand)[:120],
                  'category':_clean(category)[:160],'price':price,'regular_price':regular,
                  'promo_price':price if regular and price<regular else None,'currency':'THB','sku':sku[:100],
                  'image_url':str(image)[:800],'source_url':url or source_url,'source_tag':'Product',
                  'provenance':'gourmet-graphql-product','parser_mode':'graphql'})
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(obj)
    return _dedup(rows)

def _graphql_docs_from_js(js):
    s=_decode_js_escapes(js or '');docs=[]
    for m in re.finditer(r'\bquery\s+([A-Za-z_][A-Za-z0-9_]*)[^{}]{0,800}\{',s):
        start=m.start();brace=s.find('{',m.start());depth=0;quote='';esc=False;end=None
        for i in range(brace,min(len(s),brace+18000)):
            c=s[i]
            if quote:
                if esc:esc=False
                elif c=='\\':esc=True
                elif c==quote:quote=''
                continue
            if c in ('"',"'"):quote=c;continue
            if c=='{':depth+=1
            elif c=='}':
                depth-=1
                if depth==0:end=i+1;break
        if end:
            q=s[start:end]
            if q not in docs:docs.append(q)
        if len(docs)>=30:break
    return docs

def _gourmet_query_variables(query):
    vars={};unknown=[]
    head=query[:query.find('{')] if '{' in query else query
    for name,typ,default in re.findall(r'\$([A-Za-z_]\w*)\s*:\s*([\[\]!A-Za-z0-9_]+)(?:\s*=\s*([^,)]+))?',head):
        if default:continue
        low=name.lower();required='!' in typ
        if any(k in low for k in ('limit','pagesize','first','take','size')):vars[name]=20
        elif low in ('page','pageno','pagenumber'):vars[name]=1
        elif any(k in low for k in ('offset','skip')):vars[name]=0
        elif any(k in low for k in ('lang','locale','language')):vars[name]='th'
        elif any(k in low for k in ('search','keyword','query','term')):vars[name]=''
        elif any(k in low for k in ('country','countrycode')):vars[name]='TH'
        elif required:unknown.append(name)
    return vars,unknown

def _gourmet_bundle_queries(max_pages=3):
    r=get(GOURMET_HOME,timeout=12);diag=[];docs=[];scripts=[]
    if not r.get('ok'):return docs,scripts,[{'stage':'gourmet-bundle','status':'failed','error':r.get('error')}]
    for m in re.finditer(r"<script[^>]+src=[\"']([^\"']+)[\"']",r.get('text') or '',re.I):
        u=urljoin(r.get('final_url') or GOURMET_HOME,m.group(1))
        if u not in scripts:scripts.append(u)
    for u in scripts[:max(8,min(18,max_pages*5))]:
        rr=get(u,timeout=12,headers={'Accept':'*/*'})
        if not rr.get('ok'):
            diag.append({'stage':'gourmet-bundle','url':u,'status':'failed','error':rr.get('error')});continue
        q=_graphql_docs_from_js(rr.get('text') or '')
        docs.extend(x for x in q if x not in docs)
        diag.append({'stage':'gourmet-bundle','url':u,'status':'fetched','bytes':rr.get('bytes'),'graphql_documents':len(q)})
    return docs,scripts,diag

def gourmet_graphql_catalog(seed=GOURMET_HOME,max_pages=3,source_id=None,progressive=False,operational_config=None,stable_sample=False):
    cfg=dict(operational_config or {});endpoint=cfg.get('graphql_endpoint') or GOURMET_GRAPHQL
    rows=[];diag=[];checked=[];best_query=cfg.get('graphql_query') or '';best_vars=cfg.get('graphql_variables') or {}
    probe=_gourmet_post_json(endpoint,{'query':'query KU2DProbe { __typename }'},timeout=12);checked.append(endpoint)
    diag.append({'stage':'graphql-probe','url':endpoint,'status':'ok' if probe.get('ok') else 'failed','http_status':probe.get('status'),'error':probe.get('error'),'bytes':probe.get('bytes',0)})
    candidates=[]
    if best_query:candidates.append(best_query)
    docs,scripts,bdiag=_gourmet_bundle_queries(max_pages);diag+=bdiag
    for q in docs:
        if re.search(r'product|catalog|search|category|recommend|home|promotion',q,re.I) and q not in candidates:candidates.append(q)
    max_probe=max(3,min(8,max_pages*2))
    successful_op='';successful_vars={}
    for q in candidates[:max_probe]:
        vars,unknown=_gourmet_query_variables(q)
        if best_query and q==best_query:vars=best_vars or vars;unknown=[]
        op=(re.search(r'\bquery\s+([A-Za-z_]\w*)',q) or [None,'anonymous'])[1]
        if unknown:
            diag.append({'stage':'graphql-operation','operation':op,'status':'skipped-required-vars','required_vars':unknown[:8]});continue
        rr=_gourmet_post_json(endpoint,{'query':q,'variables':vars},timeout=15)
        if not rr.get('ok'):
            diag.append({'stage':'graphql-operation','operation':op,'status':'failed','http_status':rr.get('status'),'error':rr.get('error')});continue
        obj=rr.get('json');found=_gourmet_graphql_rows(obj,endpoint) if obj is not None else []
        errs=(obj or {}).get('errors') if isinstance(obj,dict) else None
        diag.append({'stage':'graphql-operation','operation':op,'status':'json','products':len(found),'errors':len(errs or []),'bytes':rr.get('bytes',0)})
        if found:
            rows.extend(found);successful_op=op;successful_vars=vars;best_query=q
            if len(rows)>=max(3,min(20,max_pages*4)):break
    rows=_dedup(rows)
    if stable_sample:rows=sorted(rows,key=lambda r:(r.get('sku') or '',r.get('product_name') or ''))
    target=max(3,min(len(rows),max_pages*4)) if progressive else max(3,min(len(rows),max_pages))
    if target:rows=rows[:target]
    price_pct=round(100*sum(r.get('price') is not None for r in rows)/len(rows),1) if rows else 0
    sku_pct=round(100*sum(bool(r.get('sku')) for r in rows)/len(rows),1) if rows else 0
    qhash=hashlib.sha256(best_query.encode('utf-8')).hexdigest()[:16] if best_query else ''
    opcfg={'graphql_endpoint':endpoint,'graphql_operation':successful_op,'graphql_query_hash':qhash,'graphql_query':best_query,'graphql_variables':successful_vars,
           'commerce_surface':GOURMET_HOME,'official_domain':'gourmetmarketthailand.com'}
    return {'rows':rows,'diagnostics':diag,'urls_checked':checked+scripts[:10],
      'potential':{'product_records':len(rows),'price_completeness_pct':price_pct,'sku_completeness_pct':sku_pct,
        'graphql_documents_discovered':len(docs),'graphql_operations_probed':min(len(candidates),max_probe),
        'graphql_probe_ok':bool(probe.get('ok')),'confidence':'high' if rows and price_pct>=90 and sku_pct>=80 else 'medium' if probe.get('ok') or docs else 'low',
        'operational_config':opcfg,'data_fields':['product name','SKU/GTIN','brand','category','current price','regular price','product URL'],
        'basis':'official Gourmet Market GraphQL endpoint + public Next.js query documents'}}

def gourmet_rendered_catalog(seed=GOURMET_HOME,max_pages=3,source_id=None,progressive=False,operational_config=None,stable_sample=False):
    x=browser_render(GOURMET_HOME,timeout=34);diag=[]
    if not x.get('available') or not x.get('html'):
        return {'rows':[],'diagnostics':[{'stage':'gourmet-rendered','status':'failed','error':x.get('error')}],'urls_checked':[],
          'potential':{'product_records':0,'confidence':'low','basis':'rendered Gourmet Market product cards with GTIN-bearing official product images'}}
    rows,stats=_gourmet_product_rows_from_rendered(x.get('html') or '',GOURMET_HOME)
    if stable_sample:rows=sorted(rows,key=lambda r:(r.get('sku') or '',r.get('product_name') or ''))
    target=max(5,min(len(rows),max_pages*4)) if progressive else max(3,min(len(rows),max_pages*3))
    rows=rows[:target] if target else rows
    price_pct=round(100*sum(r.get('price') is not None for r in rows)/len(rows),1) if rows else 0
    sku_pct=round(100*sum(bool(r.get('sku')) for r in rows)/len(rows),1) if rows else 0
    diag.append({'stage':'gourmet-rendered','status':'fetched','browser':x.get('exe'),'dom_bytes':len(x.get('html') or ''),**stats})
    return {'rows':rows,'diagnostics':diag,'urls_checked':[GOURMET_HOME],
      'potential':{'product_records':len(rows),'price_completeness_pct':price_pct,'sku_completeness_pct':sku_pct,
        'rendered_product_images':stats.get('gtin_images',0),'confidence':'high' if rows and price_pct>=90 and sku_pct>=90 else 'medium' if rows else 'low',
        'operational_config':{'catalog_url':GOURMET_HOME,'identity_source':'official-product-image-gtin','commerce_surface':GOURMET_HOME,'official_domain':'gourmetmarketthailand.com'},
        'data_fields':['product name','SKU/GTIN','current price','regular price','product URL','image URL'],
        'basis':'rendered Gourmet Market product cards + GTIN-bearing official product images'}}

def gourmet_promotion_surface(max_pages=3):
    x=browser_render(GOURMET_HOME,timeout=34);rows=[];diag=[]
    if not x.get('available') or not x.get('html') or not BeautifulSoup:
        return {'rows':[],'diagnostics':[{'stage':'gourmet-promotion','status':'failed','error':x.get('error')}],'urls_checked':[],
          'potential':{'promotion_records':0,'confidence':'low','basis':'official Gourmet Market rendered promotion/brochure surfaces'}}
    html=x.get('html') or '';soup=BeautifulSoup(html,'html.parser');seen=set()
    # Explicit promotion/campaign/brochure links or banners only. Category/product alt text is not a promotion.
    for el in soup.find_all(['a','img']):
        href=str(el.get('href') or '') if el.name=='a' else ''
        src=str(el.get('src') or '') if el.name=='img' else ''
        text=_clean((el.get('alt') or el.get('title') or '') if el.name=='img' else el.get_text(' ',strip=True))
        signal=' '.join((href,src,text))
        if not re.search(r'promotion|promo|campaign|brochure|deal|offer|discount|โปรโม',signal,re.I):continue
        if '/products/' in signal:continue
        if not text or text.lower() in {'brochure','promotion','promo','banner','search button'}:continue
        u=urljoin(GOURMET_HOME,href) if href else GOURMET_HOME
        key=(text,u)
        if key in seen:continue
        seen.add(key)
        rows.append({'record_type':'PromotionCandidate','promotion_title':text[:220],'offer':text[:300],'terms':'',
          'start_date':'','end_date':'','source_url':u,'source_tag':'Marketing','provenance':'gourmet-official-promotion'})
    # A product card with a source-stated crossed-out/original price is itself a valid product promotion.
    products,_=_gourmet_product_rows_from_rendered(html,GOURMET_HOME)
    for r in products:
        if r.get('regular_price') and r.get('price') is not None and r['price']<r['regular_price']:
            title=r.get('product_name') or 'Product promotion'
            rows.append({'record_type':'PromotionCandidate','promotion_title':title[:220],
              'offer':f"฿{r['price']:g} (regular ฿{r['regular_price']:g})",'terms':'','start_date':'','end_date':'',
              'source_url':r.get('source_url') or GOURMET_HOME,'source_tag':'Marketing','provenance':'gourmet-product-price-promotion'})
    rows=_dedup(rows)[:max(4,min(30,max_pages*8))]
    diag.append({'stage':'gourmet-promotion','status':'fetched','promotion_records':len(rows),'browser':x.get('exe'),'dom_bytes':len(html)})
    return {'rows':rows,'diagnostics':diag,'urls_checked':[GOURMET_HOME],
      'potential':{'promotion_records':len(rows),'confidence':'high' if len(rows)>=3 else 'medium' if rows else 'low',
        'basis':'official Gourmet Market rendered promotion/brochure surfaces + source-stated product price promotions'}}

def gourmet_catalog_network(max_pages=3):
    net=browser_netlog(GOURMET_HOME,timeout=38);diag=[];apis=[];gtins=[]
    pool=net.get('all_network_urls') or net.get('network_urls') or []
    for u in pool:
        if re.search(r'api-stark\.gourmetmarketthailand\.com/graphql',u,re.I) and u not in apis:apis.append(GOURMET_GRAPHQL)
        g,_=_gourmet_gtin_from_image(u)
        if g and g not in gtins:gtins.append(g)
    if GOURMET_GRAPHQL not in apis:apis.append(GOURMET_GRAPHQL)
    probe=_gourmet_post_json(GOURMET_GRAPHQL,{'query':'query KU2DProbe { __typename }'},timeout=12)
    diag.append({'stage':'gourmet-network','status':'captured' if net.get('available') else 'failed',
      'network_urls':len(net.get('network_urls') or []),'all_network_urls':len(pool),'graphql_candidates':len(apis),
      'product_gtin_candidates':len(gtins),'graphql_probe_ok':bool(probe.get('ok')),'graphql_http_status':probe.get('status'),
      'browser':net.get('exe'),'error':net.get('error')})
    rows=[{'record_type':'EndpointCandidate','title':u,'source_url':u,'source_tag':'Technical','provenance':'gourmet-network'} for u in apis[:6]]
    return {'rows':rows,'diagnostics':diag,'urls_checked':apis[:6],
      'potential':{'api_candidates':len(apis),'product_identity_candidates':len(gtins),'discovered_urls':len(pool),
        'graphql_probe_ok':bool(probe.get('ok')),'confidence':'high' if probe.get('ok') and gtins else 'medium' if apis or gtins else 'low',
        'candidate_sample':apis[:6],'gtin_sample':gtins[:12],
        'basis':'browser network on official Gourmet Market commerce infrastructure + read-only GraphQL probe'}}
