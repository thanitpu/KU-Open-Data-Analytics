from __future__ import annotations
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/'acquisition',ROOT/'repository'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from actual_acquisition import fetch,parse_page
from pagination_monitor import normalized_text_hash,discover_pagination
from operations_store import frontier_next,frontier_add,frontier_mark_observation,frontier_mark_check_failure,pagination_coverage,product_observation_summary

def check_source_changes(source,max_pages=25,delay_seconds=0,progress=None):
    source_id=source['source_id'];limit=max(1,min(int(max_pages),100))
    rows=frontier_next(source_id,limit)
    # If frontier is empty, establish source homepage as the first baseline.
    if not rows:rows=[{'canonical_url':source.get('url'),'pagination_group':None,'page_number':None}]
    stats={'checked':0,'baseline':0,'changed':0,'unchanged':0,'failed':0,'new_urls_discovered':0}
    details=[];started=time.time()
    for i,row in enumerate(rows,1):
        u=row.get('canonical_url') or source.get('url')
        if i>1 and delay_seconds:time.sleep(max(0,float(delay_seconds)))
        if progress:
            try:progress({'pages_done':i-1,'pages_target':len(rows),'current_url':u,'message':f'Checking {i} of {len(rows)} known pages'})
            except Exception:pass
        r=fetch(u,timeout=12)
        stats['checked']+=1
        if not r.get('ok') or 'html' not in str(r.get('content_type','')).lower():
            stats['failed']+=1;frontier_mark_check_failure(source_id,u,r.get('status',0))
            details.append({'url':u,'status':'failed','http_status':r.get('status'),'error':r.get('error')});continue
        parsed=parse_page(r['final_url'],r['text']);h=normalized_text_hash(parsed['text'])
        pag=discover_pagination(r['final_url'],parsed['links'])
        if pag:stats['new_urls_discovered']+=frontier_add(source_id,pag,r['final_url'])
        group=row.get('pagination_group');page_no=row.get('page_number');total=None
        # Prefer metadata detected from the current page.
        if pag:
            groups=[x for x in pag if not group or x.get('pagination_group')==group]
            if groups:
                group=groups[0].get('pagination_group') or group
                total=max((x.get('detected_total_pages') or 0) for x in groups) or None
        obs=frontier_mark_observation(source_id,r['final_url'],h,r.get('status',200),0,group,page_no,total,acquired=False)
        state='changed' if obs['changed'] else 'unchanged' if obs['unchanged'] else 'baseline'
        stats[state]+=1
        details.append({'url':r['final_url'],'status':state,'http_status':r.get('status',200),
                        'pagination_group':group,'page_number':page_no,'detected_total_pages':total})
        if progress:
            try:progress({'pages_done':i,'pages_target':len(rows),'current_url':r['final_url'],
                          'changed':stats['changed'],'unchanged':stats['unchanged'],'baseline':stats['baseline'],
                          'message':f"{stats['changed']} changed · {stats['unchanged']} unchanged · {stats['baseline']} baseline"})
            except Exception:pass
    coverage=pagination_coverage(source_id)
    return {'source_id':source_id,'source_name':source.get('name') or source.get('business'),
            'stats':stats,'acquisition_required':stats['changed']+stats['baseline']>0,
            'changed_urls':[x['url'] for x in details if x['status']=='changed'],
            'baseline_urls':[x['url'] for x in details if x['status']=='baseline'],
            'details':details,'pagination_coverage':coverage,
            'product_observations':product_observation_summary(source_id),
            'elapsed_seconds':round(time.time()-started,2),
            'interpretation':'A baseline page has not been compared before; it is not evidence of change. Changed means the normalized public HTML text hash differs from the prior successful check.'}
