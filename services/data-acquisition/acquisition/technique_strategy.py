from __future__ import annotations
import math,re,time,urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed

from lotus_multitechnique import run as lotus_run, TECHNIQUES as LOTUS_TECHNIQUES
from lotus_multitechnique import basic_crawler, structured_data
from lotus_multitechnique import _lotus_product_record, _lotus_promotion_record
from lotus_advanced import get, json_objects, scan_json, extract_urls, browser_render, browser_netlog, probe_json_endpoints, script_bundle_mining, robots_sitemaps
from actual_acquisition import parse_page
from unified_acquisition import acquire as generic_acquire
from supermarket_techniques import (bigc_product_catalog,bigc_promotion_surface,bigc_catalog_network,
    makro_pro_catalog,makro_promotion_catalogue,makro_pro_network,
    tops_product_catalog,tops_campaign_catalog,tops_promotion_surface,tops_catalog_network,
    gourmet_graphql_catalog,gourmet_rendered_catalog,gourmet_promotion_surface,gourmet_catalog_network)
from gourmet_detail_technique import gourmet_product_detail_catalog

GENERIC_TECHNIQUES=[
 {"key":"basic_crawler","label":"Basic HTML Crawler","kind":"content"},
 {"key":"structured_data","label":"Structured / Embedded Data","kind":"content"},
 {"key":"generic_document","label":"Readable Document Extraction","kind":"content"},
 {"key":"generic_sitemap","label":"Robots / Sitemap Discovery","kind":"discovery"},
 {"key":"generic_app_bundle","label":"JavaScript / App Bundle Mining","kind":"discovery"},
 {"key":"generic_browser_rendered","label":"Browser-rendered DOM","kind":"content"},
 {"key":"generic_browser_network","label":"Browser Network / API Discovery","kind":"discovery"},
 {"key":"generic_api_probe","label":"Discovered JSON/API Probe","kind":"content"},
]
BIGC_TECHNIQUES=[
 {"key":"bigc_product_catalog","label":"Big C Sitemap Product Detail Catalog","kind":"content"},
 {"key":"bigc_promotion_surface","label":"Big C Official Campaign Surface","kind":"content"},
 {"key":"bigc_catalog_network","label":"Big C Catalog Network / API Probe","kind":"discovery"},
]
MAKRO_TECHNIQUES=[
 {"key":"makro_pro_catalog","label":"Makro PRO Product Catalog Surface","kind":"content"},
 {"key":"makro_promotion_catalogue","label":"Makro Promotions Catalogue Surface","kind":"content"},
 {"key":"makro_pro_network","label":"Makro PRO Network / API Probe","kind":"discovery"},
]
TOPS_TECHNIQUES=[
 {"key":"tops_product_catalog","label":"Tops Sitemap Product Detail Catalog","kind":"content"},
 {"key":"tops_campaign_catalog","label":"Tops Campaign Product & Price Surface","kind":"content"},
 {"key":"tops_promotion_surface","label":"Tops Official Campaign Surface","kind":"content"},
 {"key":"tops_catalog_network","label":"Tops Catalog API / App Discovery","kind":"discovery"},
]
GOURMET_TECHNIQUES=[
 {"key":"gourmet_graphql_catalog","label":"Gourmet Market GraphQL Product Catalog","kind":"content"},
 {"key":"gourmet_product_detail_catalog","label":"Gourmet Market Official Product Detail Catalog","kind":"content"},
 {"key":"gourmet_rendered_catalog","label":"Gourmet Market Rendered Product Cards","kind":"content"},
 {"key":"gourmet_promotion_surface","label":"Gourmet Market Official Promotion Surface","kind":"content"},
 {"key":"gourmet_catalog_network","label":"Gourmet GraphQL / Network Catalog Discovery","kind":"discovery"},
]

TECHNIQUE_ENGINE_VERSION='0.24'

FACT_TYPES={"ProductCandidate","PriceCandidate","PromotionCandidate","MenuCandidate","product","price","promotion","menu_item"}
USEFUL_TYPES=FACT_TYPES|{"PromotionListingItemCandidate","DocumentCandidate","ContentCandidate","ProductURLCandidate","PromotionURLCandidate","EndpointCandidate","OfficialURLCandidate","URLCandidate"}

def host(url):
    try:return urllib.parse.urlparse(url).netloc.lower().removeprefix('www.')
    except:return ''
def base_domain(url):
    h=host(url);parts=h.split('.') if h else []
    if len(parts)<2:return h
    # Thailand (and a few common ccTLD) public suffixes are two labels.  Treating
    # every *.co.th host as the same site would both break source detection and
    # make same-site API filtering too permissive.
    two_label_suffixes={'co.th','or.th','ac.th','go.th','in.th','mi.th','net.th','co.uk','org.uk','com.au','com.sg','com.my'}
    suffix='.'.join(parts[-2:])
    if suffix in two_label_suffixes and len(parts)>=3:return '.'.join(parts[-3:])
    return suffix
def same_site(a,b):
    ba,bb=base_domain(a),base_domain(b);return bool(ba and bb and ba==bb)
def is_lotus(url):return base_domain(url)=='lotuss.com'
def is_bigc(url):return base_domain(url)=='bigc.co.th'
def is_makro(url):return base_domain(url) in {'makro.co.th','makro.pro'}
def is_tops(url):return base_domain(url)=='tops.co.th'
def is_gourmet(url):return base_domain(url)=='gourmetmarketthailand.com'
def dedup(rows):
    out=[];seen=set()
    for r in rows or []:
        k=(r.get('record_type'),r.get('source_url') or r.get('url'),r.get('product_name') or r.get('promotion_title') or r.get('title') or r.get('name'))
        if k in seen:continue
        seen.add(k);out.append(r)
    return out
def type_counts(rows):
    d={}
    for r in rows or []:d[r.get('record_type','Unknown')]=d.get(r.get('record_type','Unknown'),0)+1
    return [{"type":k,"count":v} for k,v in sorted(d.items())]
def result(key,label,status,records=None,pages=0,diag=None,elapsed=0,urls=None,note='',potential=None):
    rows=dedup(records or [])
    return {"technique":key,"label":label,"status":status,"record_count":len(rows),"record_types":type_counts(rows),"sample_records":rows[:50],"pages_checked":pages,"elapsed_seconds":round(elapsed,2),"urls_checked":urls or [],"diagnostics":diag or [],"note":note,"potential":potential or {}}

def generic_document(url,domain,purpose):
    t=time.time();x=generic_acquire(url,domain,purpose,'web')
    if not x.get('ok'):return result('generic_document','Readable Document Extraction','failed',diag=[{'url':url,'error':x.get('error')}],elapsed=time.time()-t)
    raw=x.get('raw_text') or ''
    row={"record_type":"DocumentCandidate","title":x.get('title') or host(url),"source_url":x.get('source_url') or url,"text":raw[:6000],"source_tag":"Document","provenance":"generic-document"}
    return result('generic_document','Readable Document Extraction','completed',[row] if raw.strip() else [],1,[{'url':url,'text_length':len(raw),'parser_method':x.get('parser_method')}],time.time()-t,[url],
                  'Captures readable source content when a more structured extractor is not available.',
                  {'discovered_urls':1,'estimated_extractable_records_low':1 if raw.strip() else 0,'estimated_extractable_records_high':1 if raw.strip() else 0,'confidence':'high' if raw.strip() else 'low','data_fields':['title','readable text','source URL'],'basis':'direct readable-content extraction from the supplied URL'})

def generic_sitemap(url,max_pages=3):
    t=time.time();u=urllib.parse.urlparse(url);origin=f'{u.scheme or "https"}://{u.netloc}';roots=[origin+'/robots.txt',origin+'/sitemap.xml',origin+'/sitemap_index.xml']
    maps=[];urls=[];diag=[]
    for rurl in roots:
        r=get(rurl,timeout=10)
        if not r.get('ok'):diag.append({'url':rurl,'status':'failed','error':r.get('error')});continue
        txt=r.get('text') or '';diag.append({'url':rurl,'status':'fetched','bytes':r.get('bytes',0)})
        if rurl.endswith('robots.txt'):
            maps += re.findall(r'^\s*Sitemap:\s*(https?://\S+)',txt,re.I|re.M)
        else:maps.append(r.get('final_url') or rurl)
    queue=[]
    for m in maps:
        if m not in queue:queue.append(m)
    seen=set();cap=max(6,min(25,max_pages*4))
    while queue and len(seen)<cap:
        m=queue.pop(0)
        if m in seen:continue
        seen.add(m);r=get(m,timeout=12)
        if not r.get('ok'):continue
        locs=re.findall(r'<loc>\s*(.*?)\s*</loc>',r.get('text') or '',re.I|re.S)
        for loc in locs:
            loc=loc.replace('&amp;','&').strip()
            if loc.endswith('.xml') and len(seen)+len(queue)<cap:queue.append(loc)
            elif same_site(loc,url):urls.append(loc)
    urls=list(dict.fromkeys(urls));rows=[{'record_type':'URLCandidate','title':x.rsplit('/',1)[-1] or x,'source_url':x,'source_tag':'Discovery','provenance':'official-sitemap'} for x in urls[:12]]
    return result('generic_sitemap','Robots / Sitemap Discovery','completed',rows,len(seen),diag,time.time()-t,list(seen)[:30],
                  'Official robots/sitemap coverage is discovery evidence; URL candidates are not yet business facts.',
                  {'discovered_urls':len(urls),'estimated_extractable_records_low':0,'estimated_extractable_records_high':len(urls) or None,'confidence':'high' if urls else 'low','data_fields':['official detail URL'],'basis':'official robots.txt and sitemap XML'})

def generic_app_bundle(url,max_pages=3):
    t=time.time();x=script_bundle_mining(url,max_scripts=max(6,min(18,max_pages*3)))
    cand=[u for u in x.get('candidate_urls') or [] if same_site(u,url)];apis=[u for u in x.get('api_candidates') or [] if same_site(u,url)]
    rows=dedup(x.get('rows') or [])
    if not rows:
        rows=[{'record_type':'EndpointCandidate','title':u[:220],'source_url':u,'source_tag':'Technical','provenance':'app-bundle'} for u in apis[:12]]
    met=x.get('metrics') or {};upper=met.get('reported_total') or met.get('max_array_len') or len(cand) or None
    return result('generic_app_bundle','JavaScript / App Bundle Mining','completed',rows,len(x.get('scripts') or []),x.get('diagnostics'),time.time()-t,x.get('scripts') or [],
                  'Mines publicly delivered application state and JavaScript assets for structured objects, routes and API candidates.',
                  {'discovered_urls':len(cand),'api_candidates':len(apis),'reported_total':met.get('reported_total'),'largest_embedded_array':met.get('max_array_len'),'estimated_extractable_records_low':len([r for r in rows if r.get('record_type') in FACT_TYPES]),'estimated_extractable_records_high':upper,'confidence':'high' if met.get('reported_total') else ('medium' if cand or apis or rows else 'low'),'data_fields':['structured objects','detail URLs','API candidates','pagination/count metadata'],'basis':'official HTML/application JSON/JavaScript bundles'})

def generic_browser_rendered(url):
    t=time.time();x=browser_render(url,timeout=30)
    if not x.get('available'):return result('generic_browser_rendered','Browser-rendered DOM','unavailable',diag=[{'url':url,'error':x.get('error')}],elapsed=time.time()-t)
    html=x.get('html') or '';urls=[u for u in x.get('urls') or [] if same_site(u,url)];rows=dedup(x.get('rows') or [])
    if html.strip():
        p=parse_page(url,html);text=p.get('text') or ''
        if text.strip():rows.append({'record_type':'DocumentCandidate','title':p.get('title') or host(url),'source_url':url,'text':text[:6000],'source_tag':'Rendered','provenance':'browser-rendered-dom'})
    return result('generic_browser_rendered','Browser-rendered DOM','completed' if x.get('ok') else 'failed',rows,1,[{'url':url,'browser':x.get('exe'),'dom_bytes':len(html),'same_site_urls':len(urls),'error':x.get('error') or x.get('stderr')}],time.time()-t,urls[:30],
                  'Executes client-side JavaScript in local Chrome/Edge and inspects the rendered DOM.',
                  {'discovered_urls':len(urls),'estimated_extractable_records_low':1 if html.strip() else 0,'estimated_extractable_records_high':max(1,len(urls)) if html.strip() else None,'confidence':'medium' if html.strip() else 'low','data_fields':['rendered text','rendered links','client-side content'],'basis':'DOM after JavaScript execution'})

def generic_browser_network(url):
    t=time.time();x=browser_netlog(url,timeout=35)
    if not x.get('available'):return result('generic_browser_network','Browser Network / API Discovery','unavailable',diag=[{'url':url,'error':x.get('error')}],elapsed=time.time()-t)
    net=[u for u in x.get('network_urls') or [] if same_site(u,url)];apis=[u for u in x.get('api_candidates') or [] if same_site(u,url)]
    rows=[{'record_type':'EndpointCandidate','title':u[:220],'source_url':u,'source_tag':'Technical','provenance':'browser-netlog'} for u in apis[:12]]
    return result('generic_browser_network','Browser Network / API Discovery','completed',rows,1,[{'url':url,'browser':x.get('exe'),'network_urls':len(net),'api_candidates':len(apis),'error':x.get('error') or x.get('stderr')}],time.time()-t,apis[:30],
                  'Captures same-site network requests made by the browser; candidates are not data until a bounded probe succeeds.',
                  {'discovered_urls':len(net),'api_candidates':len(apis),'estimated_extractable_records_low':0,'estimated_extractable_records_high':None,'confidence':'medium' if apis else 'low','data_fields':['XHR/fetch URL','API/search/catalog endpoint candidate'],'basis':'local Chrome/Edge network log'})

def generic_api_probe(url,max_pages=3):
    t=time.time();x=script_bundle_mining(url,max_scripts=max(6,min(16,max_pages*3)));candidates=[u for u in x.get('api_candidates') or [] if same_site(u,url) and not any(c in u for c in '{}<>')]
    p=probe_json_endpoints(candidates,max_endpoints=max(6,min(18,max_pages*3)));rows=dedup(p.get('rows') or []);met=p.get('metrics') or {};upper=met.get('reported_total') or met.get('max_array_len')
    return result('generic_api_probe','Discovered JSON/API Probe','completed',rows,len(p.get('urls_checked') or []),(x.get('diagnostics') or [])+(p.get('diagnostics') or []),time.time()-t,p.get('urls_checked') or [],
                  'Read-only probes of same-site API candidates discovered from public application assets.',
                  {'discovered_urls':len(candidates),'api_candidates_probed':len(p.get('urls_checked') or []),'reported_total':met.get('reported_total'),'reported_pages':met.get('reported_pages'),'estimated_extractable_records_low':len(rows),'estimated_extractable_records_high':upper,'confidence':'high' if upper and rows else ('medium' if rows else 'low'),'data_fields':['structured API records','pagination/count metadata'],'basis':'successful JSON responses from official same-site endpoints'})

def _special_result(key,label,x):
    rows=x.get('rows') or [];p=x.get('potential') or {}
    return result(key,label,'completed',rows,len(x.get('urls_checked') or []),x.get('diagnostics') or [],0,x.get('urls_checked') or [],p.get('basis') or '',p)

def generic_run(url,domain,purpose,max_pages=3,techniques=None,progress_callback=None):
    catalog=GENERIC_TECHNIQUES + (BIGC_TECHNIQUES if is_bigc(url) else []) + (MAKRO_TECHNIQUES if is_makro(url) else []) + (TOPS_TECHNIQUES if is_tops(url) else []) + (GOURMET_TECHNIQUES if is_gourmet(url) else [])
    chosen=techniques or [x['key'] for x in catalog]
    known={x['key'] for x in catalog};chosen=[x for x in chosen if x in known]
    funcs={
      'basic_crawler':lambda:basic_crawler(url,max_pages),
      'structured_data':lambda:structured_data(url),
      'generic_document':lambda:generic_document(url,domain,purpose),
      'generic_sitemap':lambda:generic_sitemap(url,max_pages),
      'generic_app_bundle':lambda:generic_app_bundle(url,max_pages),
      'generic_browser_rendered':lambda:generic_browser_rendered(url),
      'generic_browser_network':lambda:generic_browser_network(url),
      'generic_api_probe':lambda:generic_api_probe(url,max_pages),
      'bigc_product_catalog':lambda: _special_result('bigc_product_catalog','Big C Sitemap Product Detail Catalog',bigc_product_catalog(url,max_pages)),
      'bigc_promotion_surface':lambda: _special_result('bigc_promotion_surface','Big C Official Campaign Surface',bigc_promotion_surface(max_pages)),
      'bigc_catalog_network':lambda: _special_result('bigc_catalog_network','Big C Catalog Network / API Probe',bigc_catalog_network(max_pages)),
      'makro_pro_catalog':lambda: _special_result('makro_pro_catalog','Makro PRO Product Catalog Surface',makro_pro_catalog(url,max_pages)),
      'makro_promotion_catalogue':lambda: _special_result('makro_promotion_catalogue','Makro Promotions Catalogue Surface',makro_promotion_catalogue(max_pages)),
      'makro_pro_network':lambda: _special_result('makro_pro_network','Makro PRO Network / API Probe',makro_pro_network(max_pages)),
      'tops_product_catalog':lambda: _special_result('tops_product_catalog','Tops Sitemap Product Detail Catalog',tops_product_catalog(url,max_pages)),
      'tops_campaign_catalog':lambda: _special_result('tops_campaign_catalog','Tops Campaign Product & Price Surface',tops_campaign_catalog(max_pages)),
      'tops_promotion_surface':lambda: _special_result('tops_promotion_surface','Tops Official Campaign Surface',tops_promotion_surface(max_pages)),
      'tops_catalog_network':lambda: _special_result('tops_catalog_network','Tops Catalog API / App Discovery',tops_catalog_network(max_pages)),
      'gourmet_graphql_catalog':lambda: _special_result('gourmet_graphql_catalog','Gourmet Market GraphQL Product Catalog',gourmet_graphql_catalog(url,max_pages)),
      'gourmet_product_detail_catalog':lambda: _special_result('gourmet_product_detail_catalog','Gourmet Market Official Product Detail Catalog',gourmet_product_detail_catalog(url,max_pages)),
      'gourmet_rendered_catalog':lambda: _special_result('gourmet_rendered_catalog','Gourmet Market Rendered Product Cards',gourmet_rendered_catalog(url,max_pages)),
      'gourmet_promotion_surface':lambda: _special_result('gourmet_promotion_surface','Gourmet Market Official Promotion Surface',gourmet_promotion_surface(max_pages)),
      'gourmet_catalog_network':lambda: _special_result('gourmet_catalog_network','Gourmet GraphQL / Network Catalog Discovery',gourmet_catalog_network(max_pages)),
    }
    results=[]
    with ThreadPoolExecutor(max_workers=min(6,max(1,len(chosen)))) as ex:
        fut={ex.submit(funcs[k]):k for k in chosen}
        for f in as_completed(fut):
            k=fut[f]
            try:r=f.result()
            except Exception as e:
                meta=next(x for x in catalog if x['key']==k);r=result(k,meta['label'],'failed',diag=[{'error':f'{type(e).__name__}: {e}'}])
            results.append(r)
            if progress_callback:
                try:progress_callback(len(results),len(chosen),r)
                except Exception:pass
    order={x['key']:i for i,x in enumerate(catalog)};results.sort(key=lambda x:order.get(x['technique'],99))
    rows=dedup([r for x in results for r in x.get('sample_records') or []])
    return {'techniques_available':catalog,'techniques_selected':chosen,'technique_results':results,'record_count':sum(x.get('record_count',0) for x in results),'unique_sample_record_count':len(rows),'record_types':type_counts(rows),'sample_records':rows[:20]}

MATERIALIZABLE_TYPES=FACT_TYPES|{"PromotionListingItemCandidate"}
CONTEXT_TYPES={"DocumentCandidate","ContentCandidate"}
DISCOVERY_TYPES={"EndpointCandidate","ProductURLCandidate","PromotionURLCandidate","OfficialURLCandidate","URLCandidate"}

def _log_component(n,cap,scale=9):
    try:n=max(0,float(n or 0))
    except:n=0
    return min(cap,int(math.log10(n+1)*scale)) if n else 0

def technique_score_detail(x,allow_documents=False):
    """Evidence-first score used to choose a practical source technique.
    Priority: repository-ready yield > coverage > repeatability/confidence > efficiency > data richness.
    Discovery-only methods can be assigned as companions, but do not outrank a proven data-producing method merely because they enumerate many URLs.
    """
    if x.get('status') not in ('completed','success'):
        return {'score':0,'role':'failed','materializable_records':0,'breakdown':{'data_yield':0,'coverage':0,'reliability':0,'efficiency':0,'richness':0}}
    rows=x.get('sample_records') or []
    mat_types=set(MATERIALIZABLE_TYPES)|(CONTEXT_TYPES if allow_documents else set())
    mat=sum(1 for r in rows if r.get('record_type') in mat_types)
    ctx=sum(1 for r in rows if r.get('record_type') in CONTEXT_TYPES)
    disc=sum(1 for r in rows if r.get('record_type') in DISCOVERY_TYPES)
    types={r.get('type') for r in x.get('record_types') or []}
    p=x.get('potential') or {}; elapsed=max(.05,float(x.get('elapsed_seconds') or 0.05)); pages=max(1,int(x.get('pages_checked') or 0) or 1)
    role='acquisition' if mat>0 else ('context' if ctx>0 else ('discovery' if disc>0 or int(p.get('discovered_urls') or 0)>0 or int(p.get('api_candidates') or 0)>0 else 'no-output'))
    # 45 points: actual repository-ready/sample yield. Discovery candidates intentionally receive no yield credit.
    data_yield=min(45,18+_log_component(mat,27,12)) if mat else 0
    # 20 points: bounded official coverage. reported_total gets stronger evidence than an unbounded search candidate list.
    discovered=int(p.get('discovered_urls') or 0); reported=int(p.get('reported_total') or 0)
    coverage=min(20,_log_component(discovered,12,4)+(8 if reported else 0))
    # 15 points: confidence/repeatability evidence.
    reliability={'high':15,'medium':9,'low':3}.get(str(p.get('confidence') or '').lower(),5 if mat else 2)
    # 10 points: reward useful output per time/page; do not reward simply testing more pages.
    if mat:
        rps=mat/elapsed; rpp=mat/pages
        efficiency=min(10,2+int(min(4,rps*2))+int(min(4,rpp)))
    elif role=='discovery' and discovered:
        efficiency=min(6,1+int(min(5,discovered/max(1,elapsed*20))))
    else: efficiency=0
    # 10 points: distinct useful types + potential fields.
    useful_types=len(types & (MATERIALIZABLE_TYPES|CONTEXT_TYPES|DISCOVERY_TYPES)); fields=len(p.get('data_fields') or [])
    richness=min(10,useful_types*4+min(6,fields//2))
    # Discovery-only cap prevents a huge sitemap from becoming primary over a technique that already returns business facts.
    total=data_yield+coverage+reliability+efficiency+richness
    if role=='discovery': total=min(total,68)
    if role=='context': total=min(total,42)
    if role=='no-output': total=0
    return {'score':int(total),'role':role,'materializable_records':mat,'discovery_records':disc,
            'breakdown':{'data_yield':data_yield,'coverage':coverage,'reliability':reliability,'efficiency':efficiency,'richness':richness}}

def technique_score(x,allow_documents=False):
    return technique_score_detail(x,allow_documents)['score']

def recommend(results,min_count=1,max_count=3,allow_documents=False):
    ranked=[]
    for x in results or []:
        d=technique_score_detail(x,allow_documents=allow_documents);s=d['score']
        if s<=0:continue
        ranked.append({'technique':x.get('technique'),'label':x.get('label'),'score':s,'role':d['role'],
          'materializable_records':d['materializable_records'],'record_count':x.get('record_count',0),'record_types':x.get('record_types') or [],
          'potential':x.get('potential') or {},'elapsed_seconds':x.get('elapsed_seconds',0),'pages_checked':x.get('pages_checked',0),'score_breakdown':d['breakdown']})
    if not ranked:return []
    # A proven data-producing method is primary whenever one exists. Otherwise use the best discovery method as a temporary profile.
    acquisitions=sorted([z for z in ranked if z['role']=='acquisition'],key=lambda z:(-z['score'],-z['materializable_records'],z['elapsed_seconds'],z['label']))
    contexts=sorted([z for z in ranked if z['role']=='context'],key=lambda z:(-z['score'],z['elapsed_seconds'],z['label']))
    discoveries=sorted([z for z in ranked if z['role']=='discovery'],key=lambda z:(-z['score'],-int((z.get('potential') or {}).get('discovered_urls') or 0),z['elapsed_seconds'],z['label']))
    primary=(acquisitions or (contexts if allow_documents else []) or discoveries)[0];picked=[primary];covered={r.get('type') for r in primary.get('record_types') or []}
    # Add a second acquisition only when it contributes a distinct output type and remains competitive.
    for z in acquisitions:
        if z['technique']==primary['technique'] or len(picked)>=max_count:continue
        types={r.get('type') for r in z.get('record_types') or []}
        if (types-covered) and z['score']>=max(45,int(primary['score']*.62)):
            picked.append(z);covered|=types
    # Add at most one strong discovery companion if it expands coverage (e.g. sitemap) beyond the extraction technique.
    if len(picked)<max_count:
        for z in discoveries:
            if z['technique'] in {p['technique'] for p in picked}:continue
            potential=z.get('potential') or {}; discovered=int(potential.get('discovered_urls') or 0)
            if discovered>=10 or potential.get('reported_total'):
                picked.append(z);break
    return picked[:max_count]


def recommend_lotus_tracks(results):
    """Choose Best Acquisition Techniques per data objective instead of one global score.

    Lotus's exposes different public surfaces for Product/Price, Promotions, and catalog
    discovery. A promotion-heavy browser technique must therefore not displace a proven
    product-price extractor merely because it returns more rows.
    """
    items=[]
    for x in results or []:
        if x.get('status') not in ('completed','success'):continue
        samples=x.get('sample_records') or [];types={r.get('type'):int(r.get('count') or 0) for r in x.get('record_types') or []}
        products=int(types.get('ProductCandidate') or 0)+int(types.get('PriceCandidate') or 0)
        promos=int(types.get('PromotionCandidate') or 0)+int(types.get('PromotionListingItemCandidate') or 0)
        prod_samples=[r for r in samples if r.get('record_type') in ('ProductCandidate','PriceCandidate')]
        promo_samples=[r for r in samples if r.get('record_type') in ('PromotionCandidate','PromotionListingItemCandidate')]
        price_pct=(100*sum(r.get('price') is not None for r in prod_samples)/len(prod_samples)) if prod_samples else 0
        # Heuristic text extraction is useful evidence but less trustworthy than card/API/detail structured facts.
        heuristic_pct=(100*sum((r.get('provenance') or '')=='text-pattern' for r in prod_samples)/len(prod_samples)) if prod_samples else 0
        official_promo_pct=(100*sum(('my.lotuss.com' in (r.get('source_url') or '') or 'promotion-listing' in (r.get('provenance') or '')) for r in promo_samples)/len(promo_samples)) if promo_samples else 0
        p=x.get('potential') or {};elapsed=max(.1,float(x.get('elapsed_seconds') or .1));confidence={'high':15,'medium':9,'low':3}.get(str(p.get('confidence') or '').lower(),5)
        items.append({'x':x,'products':products,'promos':promos,'prod_samples':prod_samples,'promo_samples':promo_samples,
                      'price_pct':price_pct,'heuristic_pct':heuristic_pct,'official_promo_pct':official_promo_pct,
                      'elapsed':elapsed,'confidence':confidence,'discovered':int(p.get('discovered_urls') or p.get('full_catalog_product_urls_from_sitemap') or 0)})
    tracks={}

    product_candidates=[]
    for z in items:
        if z['products']<=0:continue
        key=z['x'].get('technique')
        score=min(48,18+_log_component(z['products'],30,10))
        score+=round(min(22,z['price_pct']*.22))
        score+=z['confidence']
        score+=min(8,round(z['products']/z['elapsed']*3))
        if key=='lotus_catalog_api':score+=18
        elif key=='category_product_catalog':score+=12
        elif key=='product_surface':score+=8
        elif key=='basic_crawler':score-=round(min(22,z['heuristic_pct']*.22))
        product_candidates.append((score,z))
    if product_candidates:
        score,z=max(product_candidates,key=lambda q:(q[0],q[1]['products'],-q[1]['elapsed']))
        tracks['product_price']={'track':'product_price','label':'Product & Price','technique':z['x'].get('technique'),
          'technique_label':z['x'].get('label'),'score':int(score),'records':z['products'],
          'price_completeness_pct':round(z['price_pct'],1),'confidence':(z['x'].get('potential') or {}).get('confidence'),
          'reason':'prioritizes repository-ready product rows with real prices; public catalog API/card/detail evidence outranks heuristic numeric text parsing'}

    promo_candidates=[]
    for z in items:
        if z['promos']<=0:continue
        key=z['x'].get('technique')
        score=min(48,18+_log_component(z['promos'],30,10))+z['confidence']+min(8,round(z['promos']/z['elapsed']*2))
        score+=round(min(20,z['official_promo_pct']*.20))
        if key=='official_surfaces':score+=18
        elif key=='browser_rendered':score+=8
        elif key=='app_bundle_mining':score-=15
        promo_candidates.append((score,z))
    if promo_candidates:
        score,z=max(promo_candidates,key=lambda q:(q[0],q[1]['promos'],-q[1]['elapsed']))
        tracks['promotion']={'track':'promotion','label':'Promotions','technique':z['x'].get('technique'),
          'technique_label':z['x'].get('label'),'score':int(score),'records':z['promos'],
          'official_promotion_pct':round(z['official_promo_pct'],1),'confidence':(z['x'].get('potential') or {}).get('confidence'),
          'reason':'prioritizes official promotion surfaces and promotion-specific records over generic rendered/app text'}

    discovery_candidates=[]
    for z in items:
        p=z['x'].get('potential') or {};disc=max(z['discovered'],int(p.get('api_candidates') or 0),int(p.get('network_urls') or 0))
        if disc<=0:continue
        score=_log_component(disc,45,4)+z['confidence']
        if z['x'].get('technique')=='sitemap_discovery':score+=18
        if z['x'].get('technique')=='browser_network':score+=8
        discovery_candidates.append((score,z,disc))
    if discovery_candidates:
        score,z,disc=max(discovery_candidates,key=lambda q:(q[0],q[2],-q[1]['elapsed']))
        tracks['discovery']={'track':'discovery','label':'Coverage / Discovery','technique':z['x'].get('technique'),
          'technique_label':z['x'].get('label'),'score':int(score),'discovered':disc,
          'confidence':(z['x'].get('potential') or {}).get('confidence'),
          'reason':'expands catalog/API coverage but is not treated as a business-record extractor by itself'}

    # Union techniques while preserving track ownership in the persisted evidence JSON.
    by={x.get('technique'):x for x in results or []}
    picked=[];index={}
    for track in ('product_price','promotion','discovery'):
        tr=tracks.get(track)
        if not tr:continue
        key=tr['technique'];x=by.get(key) or {}
        if key in index:
            picked[index[key]]['tracks'].append(track);picked[index[key]]['track_scores'][track]=tr['score'];continue
        d=technique_score_detail(x,allow_documents=False)
        rec={'technique':key,'label':x.get('label') or tr['technique_label'],'score':tr['score'],
             'role':'discovery' if track=='discovery' else 'acquisition',
             'materializable_records':d.get('materializable_records',0),'record_count':x.get('record_count',0),
             'record_types':x.get('record_types') or [],'potential':x.get('potential') or {},
             'elapsed_seconds':x.get('elapsed_seconds',0),'pages_checked':x.get('pages_checked',0),
             'tracks':[track],'track_scores':{track:tr['score']},'track_evidence':{track:tr}}
        index[key]=len(picked);picked.append(rec)
    return picked,tracks

def recommend_supermarket_tracks(results,family):
    items=[]
    for x in results or []:
        if x.get('status') not in ('completed','success'):continue
        types={r.get('type'):int(r.get('count') or 0) for r in x.get('record_types') or []}
        products=int(types.get('ProductCandidate') or 0)+int(types.get('PriceCandidate') or 0)
        promos=int(types.get('PromotionCandidate') or 0)+int(types.get('PromotionListingItemCandidate') or 0)
        samples=x.get('sample_records') or []
        ps=[r for r in samples if r.get('record_type') in ('ProductCandidate','PriceCandidate')]
        price_pct=(100*sum(r.get('price') is not None for r in ps)/len(ps)) if ps else 0
        noisy=lambda r: ((r.get('provenance') or '') in ('text-pattern','optimized-retail-text') or
              str(r.get('product_name') or '').strip().lower() in ('ซื้อครบ','shop','ช็อป','คูปอง') or
              bool(re.match(r'^(?:ลด|ซื้อครบ|โค้ด|coupon|discount)\b',str(r.get('product_name') or '').strip(),re.I)))
        noise=(100*sum(noisy(r) for r in ps)/len(ps)) if ps else 0
        identity=(100*sum(bool(r.get('sku')) or bool(re.search(r'/(?:product|p)/',r.get('source_url') or '',re.I)) for r in ps)/len(ps)) if ps else 0
        p=x.get('potential') or {};confidence={'high':15,'medium':9,'low':3}.get(str(p.get('confidence') or '').lower(),5)
        items.append({'x':x,'products':products,'promos':promos,'price_pct':price_pct,'noise':noise,
                      'reported_total':int(p.get('reported_total') or p.get('estimated_extractable_records_high') or 0),
                      'discovered':int(p.get('discovered_urls') or p.get('product_urls_discovered') or 0),'identity_pct':identity,'confidence':confidence})
    tracks={}
    prod=[]
    for z in items:
        if z['products']<=0:continue
        key=z['x'].get('technique')
        # Supermarket Product & Price must be traceable to an actual product identity.
        # Big C's generic text crawler is explicitly excluded because it previously
        # promoted coupon thresholds such as 'ซื้อครบ = 1' into product records.
        if family=='bigc' and key=='basic_crawler':continue
        if key not in ('bigc_product_catalog','bigc_catalog_network','makro_pro_catalog','makro_pro_network','tops_product_catalog','tops_campaign_catalog','tops_catalog_network','gourmet_graphql_catalog','gourmet_product_detail_catalog','gourmet_rendered_catalog','gourmet_catalog_network') and z.get('identity_pct',0)<75:continue
        score=min(45,18+_log_component(z['products'],27,10))+round(min(20,z['price_pct']*.20))+z['confidence']
        score+=round(min(12,z.get('identity_pct',0)*.12))
        if family=='bigc':
            if key=='bigc_product_catalog':score+=30
            elif key=='bigc_catalog_network':score+=20
        if family=='makro':
            if key=='makro_pro_catalog':score+=35
            elif key=='makro_pro_network':score+=22
        if family=='tops':
            if key=='tops_campaign_catalog':score+=38
            elif key=='tops_product_catalog':score+=34
            elif key=='tops_catalog_network':score+=20
            elif key=='basic_crawler':score-=25
        if family=='gourmet':
            if key=='gourmet_graphql_catalog':score+=60
            elif key=='gourmet_product_detail_catalog':score+=48
            elif key=='gourmet_rendered_catalog':score+=32
            elif key=='gourmet_catalog_network':score+=18
            elif key in ('generic_browser_rendered','basic_crawler'):score-=28
        prod.append((score,z))
    if prod:
        score,z=max(prod,key=lambda q:(q[0],q[1]['products']))
        tracks['product_price']={'track':'product_price','label':'Product & Price','technique':z['x'].get('technique'),
          'technique_label':z['x'].get('label'),'score':int(score),'records':z['products'],'price_completeness_pct':round(z['price_pct'],1),
          'confidence':(z['x'].get('potential') or {}).get('confidence'),'reason':'requires real product identity (SKU/product URL) and price evidence; heuristic coupon/marketing text cannot qualify as the supermarket Product & Price track'}
    prom=[]
    for z in items:
        if z['promos']<=0:continue
        key=z['x'].get('technique')
        if family=='gourmet' and key=='generic_browser_rendered':continue
        score=18+_log_component(z['promos'],30,10)+z['confidence']
        if family=='bigc' and key=='bigc_promotion_surface':score+=30
        if family=='makro' and key=='makro_promotion_catalogue':score+=30
        if family=='tops' and key=='tops_promotion_surface':score+=34
        if family=='gourmet' and key=='gourmet_promotion_surface':score+=36
        if family=='gourmet' and key=='generic_browser_rendered':score-=30
        if key=='basic_crawler':score-=10
        prom.append((score,z))
    if prom:
        score,z=max(prom,key=lambda q:(q[0],q[1]['promos']))
        tracks['promotion']={'track':'promotion','label':'Promotions','technique':z['x'].get('technique'),
          'technique_label':z['x'].get('label'),'score':int(score),'records':z['promos'],
          'confidence':(z['x'].get('potential') or {}).get('confidence'),'reason':'prefers an official campaign/catalogue surface over generic marketing-text matches'}
    disc=[]
    for z in items:
        key=z['x'].get('technique');coverage=max(z['reported_total'],z['discovered'])
        if family=='makro' and key=='makro_pro_catalog':coverage=max(coverage,z['reported_total']);bonus=30
        elif family=='tops' and key in ('generic_sitemap','tops_product_catalog'):bonus=24
        elif family=='bigc' and key in ('generic_sitemap','bigc_product_catalog'):bonus=20
        elif family=='gourmet' and key=='gourmet_catalog_network':
            coverage=max(coverage,int((z['x'].get('potential') or {}).get('product_identity_candidates') or 0));bonus=32
        elif family=='gourmet' and key in ('gourmet_graphql_catalog','gourmet_rendered_catalog'):bonus=20
        else:bonus=0
        if coverage<=0:continue
        score=_log_component(coverage,45,4)+z['confidence']+bonus
        disc.append((score,z,coverage))
    if disc:
        score,z,cov=max(disc,key=lambda q:(q[0],q[2]))
        tracks['discovery']={'track':'discovery','label':'Coverage / Discovery','technique':z['x'].get('technique'),
          'technique_label':z['x'].get('label'),'score':int(score),'discovered':cov,
          'confidence':(z['x'].get('potential') or {}).get('confidence'),'reason':'tracks the broadest official product universe/coverage surface without treating URL enumeration alone as product facts'}
    by={x.get('technique'):x for x in results or []};picked=[];pos={}
    for track in ('product_price','promotion','discovery'):
        tr=tracks.get(track)
        if not tr:continue
        key=tr['technique'];x=by.get(key) or {}
        if key in pos:
            picked[pos[key]]['tracks'].append(track);picked[pos[key]]['track_scores'][track]=tr['score'];picked[pos[key]]['track_evidence'][track]=tr;continue
        d=technique_score_detail(x,allow_documents=False)
        rec={'technique':key,'label':x.get('label') or tr['technique_label'],'score':tr['score'],
             'role':'discovery' if track=='discovery' else 'acquisition','materializable_records':d.get('materializable_records',0),
             'record_count':x.get('record_count',0),'record_types':x.get('record_types') or [],'potential':x.get('potential') or {},
             'elapsed_seconds':x.get('elapsed_seconds',0),'pages_checked':x.get('pages_checked',0),'tracks':[track],
             'track_scores':{track:tr['score']},'track_evidence':{track:tr}}
        pos[key]=len(picked);picked.append(rec)
    return picked,tracks

def applicable_techniques(url):
    if is_lotus(url):catalog=LOTUS_TECHNIQUES
    else:catalog=GENERIC_TECHNIQUES + (BIGC_TECHNIQUES if is_bigc(url) else []) + (MAKRO_TECHNIQUES if is_makro(url) else []) + (TOPS_TECHNIQUES if is_tops(url) else []) + (GOURMET_TECHNIQUES if is_gourmet(url) else []) + (GOURMET_TECHNIQUES if is_gourmet(url) else [])
    return [x.get('key') for x in catalog]

def explore_with_strategy(url,domain,purpose,max_pages=3,techniques=None,progress_callback=None):
    if is_lotus(url):
        m=lotus_run(url,max_pages,techniques,progress_callback=progress_callback)
        catalog=m.get('techniques_available') or LOTUS_TECHNIQUES
    else:
        m=generic_run(url,domain,purpose,max_pages,techniques,progress_callback=progress_callback)
        catalog=m.get('techniques_available') or (GENERIC_TECHNIQUES + (BIGC_TECHNIQUES if is_bigc(url) else []) + (MAKRO_TECHNIQUES if is_makro(url) else []) + (TOPS_TECHNIQUES if is_tops(url) else []) + (GOURMET_TECHNIQUES if is_gourmet(url) else []))
    allow_documents=purpose not in {'retail_market_intelligence','competitive_intelligence'}
    if is_lotus(url) and purpose in {'retail_market_intelligence','competitive_intelligence'}:
        recs,tracks=recommend_lotus_tracks(m.get('technique_results') or [])
        m['track_recommendations']=tracks
    elif is_bigc(url) and purpose in {'retail_market_intelligence','competitive_intelligence'}:
        recs,tracks=recommend_supermarket_tracks(m.get('technique_results') or [],'bigc');m['track_recommendations']=tracks
    elif is_makro(url) and purpose in {'retail_market_intelligence','competitive_intelligence'}:
        recs,tracks=recommend_supermarket_tracks(m.get('technique_results') or [],'makro');m['track_recommendations']=tracks
    elif is_tops(url) and purpose in {'retail_market_intelligence','competitive_intelligence'}:
        recs,tracks=recommend_supermarket_tracks(m.get('technique_results') or [],'tops');m['track_recommendations']=tracks
    elif is_gourmet(url) and purpose in {'retail_market_intelligence','competitive_intelligence'}:
        recs,tracks=recommend_supermarket_tracks(m.get('technique_results') or [],'gourmet');m['track_recommendations']=tracks
    else:
        recs=recommend(m.get('technique_results') or [],allow_documents=allow_documents)
        m['track_recommendations']={}
    for r in recs:r['engine_version']=TECHNIQUE_ENGINE_VERSION
    m['recommended_techniques']=recs
    m['assigned_techniques']=[x['technique'] for x in recs]
    m['techniques_available']=catalog
    return m

def fact_records(rows):
    out=[]
    for r in rows or []:
        if r.get('record_type') in FACT_TYPES:out.append(r)
        elif r.get('record_type')=='PromotionListingItemCandidate' and r.get('promotion_title'):
            out.append({'record_type':'PromotionCandidate','promotion_title':r.get('promotion_title'),'promotion_type':'Official promotion listing','offer':'','terms':'','source_url':r.get('source_url'),'source_tag':r.get('source_tag') or 'Marketing','provenance':r.get('provenance') or 'promotion-listing-card'})
    return dedup(out)

def _assignment_operational_config(assignment_rows,technique):
    for row in assignment_rows or []:
        if row.get('technique')!=technique:continue
        ev=row.get('evidence') or {}
        return ((ev.get('potential') or {}).get('operational_config') or
                ev.get('operational_config') or {})
    return {}

def _tech_result(key,label,records=None,pages=0,urls=None,potential=None,diagnostics=None,role='acquisition'):
    records=dedup(records or [])
    return {'technique':key,'label':label,'status':'completed','record_count':len(records),
            'record_types':type_counts(records),'sample_records':records[:50],
            'pages_checked':int(pages or 0),'elapsed_seconds':0,'urls_checked':urls or [],
            'potential':potential or {},'diagnostics':diagnostics or [],'operational_role':role}

def materialize_for_run(source,techniques,max_pages=8,assignment_rows=None,stable_sample=False):
    url=source.get('url');domain=source.get('domain') or 'General';purpose=source.get('purpose') or 'research_evidence'

    # Lotus's is executed by operational data tracks rather than re-running the full
    # Explore bench during every Audit/Acquire. This makes the audited profile the same
    # profile used for repository acquisition and reuses persisted API configuration.
    if is_lotus(url):
        rows=[];results=[];tset=set(techniques or [])
        from lotus_multitechnique import (
            lotus_catalog_api_materialize, category_product_materialize,
            official_surfaces_materialize
        )

        if 'lotus_catalog_api' in tset:
            cfg=_assignment_operational_config(assignment_rows,'lotus_catalog_api')
            api=lotus_catalog_api_materialize(url,max_pages=max_pages,source_id=source.get('source_id'),
                                               operational_config=cfg)
            api_rows=api.get('rows') or [];rows.extend(api_rows)
            tested=len(api.get('batch_skus') or [])
            success=round(100*len(api_rows)/tested,1) if tested else 0
            results.append(_tech_result('lotus_catalog_api','Lotus Catalog API',api_rows,
                len(api.get('urls_checked') or []),api.get('urls_checked') or [],
                {'api_product_records':len(api_rows),'batch_skus_tested':tested,
                 'api_materialization_success_pct':success,
                 'full_catalog_product_urls_from_sitemap':api.get('sitemap_total'),
                 'api_schema':(api.get('metrics') or {}).get('api_schema'),
                 'operational_config':api.get('operational_config') or cfg,
                 'confidence':'high' if api_rows and success>=80 else 'medium' if api_rows else 'low'},
                api.get('diagnostics') or []))

        if 'category_product_catalog' in tset:
            cat=category_product_materialize(url,max_pages=max_pages)
            cat_rows=cat.get('rows') or [];rows.extend(cat_rows)
            results.append(_tech_result('category_product_catalog','Lotus Category Product & Price Catalog',
                cat_rows,len(cat.get('urls_checked') or []),cat.get('urls_checked') or [],
                {'category_product_urls':cat.get('category_product_urls'),'confidence':'medium' if cat_rows else 'low'},
                cat.get('diagnostics') or []))

        if 'official_surfaces' in tset:
            promo=official_surfaces_materialize(max_pages=max_pages)
            promo_rows=promo.get('rows') or [];rows.extend(promo_rows)
            results.append(_tech_result('official_surfaces',"My Lotus’s Promotion Surface",
                promo_rows,len(promo.get('urls_checked') or []),promo.get('urls_checked') or [],
                {'promotion_records':len(promo_rows),'confidence':'medium' if promo_rows else 'low'},
                promo.get('diagnostics') or []))

        if 'sitemap_discovery' in tset:
            sm=robots_sitemaps(url,max_sitemaps=max(12,min(32,max_pages*5)))
            product_urls=sm.get('product_urls') or []
            results.append(_tech_result('sitemap_discovery','Robots / Sitemap Discovery',[],
                len(sm.get('sitemaps') or []),sm.get('sitemaps') or [],
                {'discovered_urls':len(sm.get('urls') or []),'product_urls':len(product_urls),
                 'confidence':'high' if product_urls else 'low'},sm.get('diagnostics') or [],role='discovery'))

        # Compatibility for an older Lotus profile: execute any unrecognized assigned
        # techniques through the bounded Explore implementation, but do not replace
        # the explicit operational tracks above.
        handled={'lotus_catalog_api','category_product_catalog','official_surfaces','sitemap_discovery'}
        remaining=[x for x in (techniques or []) if x not in handled]
        if remaining:
            extra=explore_with_strategy(url,domain,purpose,max_pages,remaining)
            results.extend(extra.get('technique_results') or [])
            rows.extend(fact_records([r for x in extra.get('technique_results') or [] for r in x.get('sample_records') or []]))

        m={'technique_results':results,'techniques_selected':list(techniques or []),
           'recommended_techniques':[],'track_recommendations':{},'operational_execution':True}
        return {'records':dedup(rows),'benchmark':m,'techniques_used':techniques or []}

    if is_bigc(url):
        rows=[];results=[];tset=set(techniques or [])
        if 'bigc_product_catalog' in tset:
            cfg=_assignment_operational_config(assignment_rows,'bigc_product_catalog')
            x=bigc_product_catalog(url,max_pages=max_pages,source_id=source.get('source_id'),progressive=True,operational_config=cfg,stable_sample=stable_sample)
            rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('bigc_product_catalog','Big C Sitemap Product Detail Catalog',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'bigc_promotion_surface' in tset:
            x=bigc_promotion_surface(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('bigc_promotion_surface','Big C Official Campaign Surface',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'bigc_catalog_network' in tset:
            x=bigc_catalog_network(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('bigc_catalog_network','Big C Catalog Network / API Probe',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or [],role='discovery' if not rr else 'acquisition'))
        if 'generic_sitemap' in tset:
            x=generic_sitemap(url,max_pages);results.append(x)
        handled={'bigc_product_catalog','bigc_promotion_surface','bigc_catalog_network','generic_sitemap'}
        remaining=[x for x in (techniques or []) if x not in handled]
        if remaining:
            extra=generic_run(url,domain,purpose,max_pages,remaining);results.extend(extra.get('technique_results') or [])
            rows.extend(fact_records([r for x in extra.get('technique_results') or [] for r in x.get('sample_records') or []]))
        m={'technique_results':results,'techniques_selected':list(techniques or []),'recommended_techniques':[],'track_recommendations':{},'operational_execution':True}
        return {'records':dedup(rows),'benchmark':m,'techniques_used':techniques or []}

    if is_makro(url):
        rows=[];results=[];tset=set(techniques or [])
        if 'makro_pro_catalog' in tset:
            cfg=_assignment_operational_config(assignment_rows,'makro_pro_catalog')
            x=makro_pro_catalog(url,max_pages=max_pages,source_id=source.get('source_id'),progressive=True,operational_config=cfg,stable_sample=stable_sample)
            rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('makro_pro_catalog','Makro PRO Product Catalog Surface',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'makro_promotion_catalogue' in tset:
            x=makro_promotion_catalogue(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('makro_promotion_catalogue','Makro Promotions Catalogue Surface',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'makro_pro_network' in tset:
            x=makro_pro_network(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('makro_pro_network','Makro PRO Network / API Probe',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or [],role='discovery' if not rr else 'acquisition'))
        if 'generic_sitemap' in tset:
            x=generic_sitemap(url,max_pages);results.append(x)
        handled={'makro_pro_catalog','makro_promotion_catalogue','makro_pro_network','generic_sitemap'}
        remaining=[x for x in (techniques or []) if x not in handled]
        if remaining:
            extra=generic_run(url,domain,purpose,max_pages,remaining);results.extend(extra.get('technique_results') or [])
            rows.extend(fact_records([r for x in extra.get('technique_results') or [] for r in x.get('sample_records') or []]))
        m={'technique_results':results,'techniques_selected':list(techniques or []),'recommended_techniques':[],'track_recommendations':{},'operational_execution':True}
        return {'records':dedup(rows),'benchmark':m,'techniques_used':techniques or []}

    if is_tops(url):
        rows=[];results=[];tset=set(techniques or [])
        if 'tops_product_catalog' in tset:
            cfg=_assignment_operational_config(assignment_rows,'tops_product_catalog')
            x=tops_product_catalog(url,max_pages=max_pages,source_id=source.get('source_id'),progressive=True,operational_config=cfg,stable_sample=stable_sample)
            rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('tops_product_catalog','Tops Sitemap Product Detail Catalog',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'tops_campaign_catalog' in tset:
            x=tops_campaign_catalog(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('tops_campaign_catalog','Tops Campaign Product & Price Surface',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'tops_promotion_surface' in tset:
            x=tops_promotion_surface(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('tops_promotion_surface','Tops Official Campaign Surface',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'tops_catalog_network' in tset:
            x=tops_catalog_network(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('tops_catalog_network','Tops Catalog API / App Discovery',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or [],role='discovery' if not rr else 'acquisition'))
        if 'generic_sitemap' in tset:
            results.append(generic_sitemap(url,max_pages))
        handled={'tops_product_catalog','tops_campaign_catalog','tops_promotion_surface','tops_catalog_network','generic_sitemap'}
        remaining=[x for x in (techniques or []) if x not in handled]
        if remaining:
            extra=generic_run(url,domain,purpose,max_pages,remaining);results.extend(extra.get('technique_results') or [])
            rows.extend(fact_records([r for x in extra.get('technique_results') or [] for r in x.get('sample_records') or []]))
        m={'technique_results':results,'techniques_selected':list(techniques or []),'recommended_techniques':[],'track_recommendations':{},'operational_execution':True}
        return {'records':dedup(rows),'benchmark':m,'techniques_used':techniques or []}

    if is_gourmet(url):
        rows=[];results=[];tset=set(techniques or [])
        if 'gourmet_graphql_catalog' in tset:
            cfg=_assignment_operational_config(assignment_rows,'gourmet_graphql_catalog')
            x=gourmet_graphql_catalog(url,max_pages=max_pages,source_id=source.get('source_id'),progressive=True,operational_config=cfg,stable_sample=stable_sample)
            rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('gourmet_graphql_catalog','Gourmet Market GraphQL Product Catalog',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'gourmet_product_detail_catalog' in tset:
            cfg=_assignment_operational_config(assignment_rows,'gourmet_product_detail_catalog')
            x=gourmet_product_detail_catalog(url,max_pages=max_pages,source_id=source.get('source_id'),progressive=True,operational_config=cfg,stable_sample=stable_sample)
            rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('gourmet_product_detail_catalog','Gourmet Market Official Product Detail Catalog',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'gourmet_rendered_catalog' in tset:
            cfg=_assignment_operational_config(assignment_rows,'gourmet_rendered_catalog')
            x=gourmet_rendered_catalog(url,max_pages=max_pages,source_id=source.get('source_id'),progressive=True,operational_config=cfg,stable_sample=stable_sample)
            rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('gourmet_rendered_catalog','Gourmet Market Rendered Product Cards',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'gourmet_promotion_surface' in tset:
            x=gourmet_promotion_surface(max_pages=max_pages);rr=x.get('rows') or [];rows.extend(rr)
            results.append(_tech_result('gourmet_promotion_surface','Gourmet Market Official Promotion Surface',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))
        if 'gourmet_catalog_network' in tset:
            x=gourmet_catalog_network(max_pages=max_pages);rr=x.get('rows') or []
            results.append(_tech_result('gourmet_catalog_network','Gourmet GraphQL / Network Catalog Discovery',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or [],role='discovery'))
        if 'generic_sitemap' in tset:results.append(generic_sitemap(url,max_pages))
        handled={'gourmet_graphql_catalog','gourmet_product_detail_catalog','gourmet_rendered_catalog','gourmet_promotion_surface','gourmet_catalog_network','generic_sitemap'}
        remaining=[x for x in (techniques or []) if x not in handled]
        if remaining:
            extra=generic_run(url,domain,purpose,max_pages,remaining);results.extend(extra.get('technique_results') or [])
            rows.extend(fact_records([r for x in extra.get('technique_results') or [] for r in x.get('sample_records') or []]))
        m={'technique_results':results,'techniques_selected':list(techniques or []),'recommended_techniques':[],'track_recommendations':{},'operational_execution':True}
        return {'records':dedup(rows),'benchmark':m,'techniques_used':techniques or []}

    # Generic/non-Lotus path keeps the adaptive bench behavior.
    m=explore_with_strategy(url,domain,purpose,max_pages,techniques)
    rows=fact_records([r for x in m.get('technique_results') or [] for r in x.get('sample_records') or []])
    return {'records':dedup(rows),'benchmark':m,'techniques_used':techniques or []}



def assigned_profile(source_id):
    """Return the persisted Best Acquisition Technique profile for a monitoring source."""
    from operations_store import technique_assignments
    rows=technique_assignments(source_id) if source_id else []
    techniques=[x.get('technique') for x in rows if x.get('technique')]
    return rows,techniques


def technique_tracks_from_assignments(rows):
    tracks={}
    for row in rows or []:
        ev=row.get('evidence') or {}
        for tr in ev.get('tracks') or []:
            tracks[tr]={'technique':row.get('technique'),'label':row.get('label'),'score':(ev.get('track_scores') or {}).get(tr,row.get('score')),
                        'evidence':(ev.get('track_evidence') or {}).get(tr)}
    return tracks

def technique_profile_fingerprint(techniques,assignment_rows=None):
    import hashlib,json
    vals=[str(x).strip() for x in (techniques or []) if str(x).strip()]
    extras=[]
    for row in assignment_rows or []:
        ev=row.get('evidence') or {}
        op=((ev.get('potential') or {}).get('operational_config') or ev.get('operational_config') or {})
        stable_op={k:op.get(k) for k in ('batch_endpoint','search_endpoint','seller_id','max_batch_size','catalog_url','category_urls','page_size','pagination_param','commerce_surface','official_related_domain','official_domain','graphql_endpoint','graphql_operation','graphql_query_hash','identity_source','seed_urls','crawl_mode') if op.get(k) is not None}
        extras.append({'technique':row.get('technique'),'tracks':ev.get('tracks') or [],
                       'engine_version':ev.get('engine_version') or TECHNIQUE_ENGINE_VERSION,
                       'operational_config':stable_op})
    payload={'engine_version':TECHNIQUE_ENGINE_VERSION,'techniques':vals,'track_profile':extras}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()[:16] if vals else None

def assigned_acquisition(source,max_pages=8,progress=None,require_profile=True,stable_sample=False):
    """Run the persisted Best Acquisition Technique profile and normalize the result.

    This is the authoritative acquisition path for Deep Audit / Deep Acquire.  It does
    not silently switch back to the legacy crawler when an assigned profile exists but
    produces no business facts; that condition must be visible to the audit/store gate.
    """
    rows,techniques=assigned_profile(source.get('source_id'))
    if require_profile and not techniques:
        raise RuntimeError('No Best Acquisition Technique is assigned. Run Find Best Data Acquisition Techniques first.')
    if not techniques:
        return None
    if progress:
        progress({'phase':'best-technique','message':'Applying Best Acquisition Technique profile','assigned_techniques':techniques})
    non_commerce=(source.get('registry') and source.get('registry')!='commerce') or source.get('purpose') in {'knowledge_learning','research_evidence','evidence_verification'}
    if non_commerce:
        doc,bench=document_from_assigned(source,techniques,min(max_pages,6))
        records=[]
        if doc and (doc.get('raw_text') or '').strip():
            records=[{'record_type':'DocumentCandidate','title':doc.get('title') or host(source.get('url')),
                      'text':doc.get('raw_text') or '','source_url':doc.get('source_url') or source.get('url'),
                      'source_tag':'Document','provenance':doc.get('parser_method') or 'assigned-technique-document'}]
        run={'records':records,'benchmark':bench or {},'techniques_used':techniques}
    else:
        run=materialize_for_run(source,techniques,max_pages,assignment_rows=rows,stable_sample=stable_sample)
        bench=run.get('benchmark') or {}
    bench=run.get('benchmark') or bench or {}
    tr=[x for x in (bench.get('technique_results') or []) if x.get('technique') in set(techniques)]
    urls=[];diagnostics=[];pages_checked=0
    for x in tr:
        pages_checked+=int(x.get('pages_checked') or 0)
        for u in x.get('urls_checked') or []:
            if u and u not in urls:urls.append(u)
        diagnostics.append({'technique':x.get('technique'),'label':x.get('label'),'status':x.get('status'),
          'record_count':x.get('record_count',0),'record_types':x.get('record_types') or [],
          'pages_checked':x.get('pages_checked',0),'elapsed_seconds':x.get('elapsed_seconds',0),
          'potential':x.get('potential') or {},'diagnostics':x.get('diagnostics') or []})
    records=dedup(run.get('records') or [])
    return {
      'records':records,'pages':[],'adapter':'best-technique:'+','.join(techniques),
      'sector':source.get('sector') or source.get('domain'),'diagnostics':diagnostics,
      'benchmark':bench,'technique_results':tr,'technique_assignments':rows,
      'assigned_techniques':techniques,'technique_tracks':technique_tracks_from_assignments(rows),'technique_profile_fingerprint':technique_profile_fingerprint(techniques,rows),
      'pages_checked':pages_checked,'urls_checked':urls,'technique_profile_applied':True,
      'legacy_fallback_used':False,
    }

def document_from_assigned(source,techniques,max_pages=4):
    """Materialize a repository-friendly document from an assigned technique profile.
    Structured/business facts are serialized only when no readable document is available, preserving provenance.
    """
    import hashlib,json
    m=explore_with_strategy(source.get('url'),source.get('domain') or 'General',source.get('purpose') or 'research_evidence',max_pages,techniques)
    rows=[r for x in m.get('technique_results') or [] for r in x.get('sample_records') or []]
    doc=next((r for r in rows if r.get('record_type')=='DocumentCandidate' and (r.get('text') or '').strip()),None)
    if doc:
        text=doc.get('text') or '';title=doc.get('title') or host(source.get('url'))
    else:
        facts=fact_records(rows)
        if not facts:return None,m
        text=json.dumps(facts,ensure_ascii=False,indent=2);title=(source.get('name') or host(source.get('url'))) + ' structured acquisition'
    return {'ok':True,'source_url':source.get('url'),'canonical_url':source.get('url'),'title':title,'raw_text':text,
            'source_type':source.get('source_type') or 'web','domain':source.get('domain') or 'General','purpose':source.get('purpose') or 'research_evidence',
            'http_status':200,'parser_method':'assigned-technique:'+','.join(techniques or []),'content_hash':hashlib.sha256(text.encode('utf-8')).hexdigest()},m
