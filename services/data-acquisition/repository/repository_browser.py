from __future__ import annotations

# Read-only repository browsing and coverage summaries for the Data Acquisition UI.

MASTER_REFERENCE={
    'business':'Businesses',
    'location':'Locations',
    'channel':'Channels',
    'canonical_product':'Product Master',
    'entity_resolution_map':'Product Resolution Map',
    'topic':'Topics / Taxonomy',
    'learning_journey_step':'Journey Steps',
    'place':'Places',
    'equipment_knowledge':'Equipment Reference',
    'knowledge_entity':'Knowledge Entities',
    'source_assessment':'Source Assessments',
}
TRANSACTIONAL={
    'listing':'Listings',
    'price_version':'Price History',
    'promotion':'Promotions',
    'promotion_offer':'Promotion Offers',
    'marketplace_signal':'Marketplace Signals',
    'evidence':'Source Evidence',
    'content_item':'Acquired Content',
    'acquired_document':'Acquired Documents',
}
TECHNICAL_DERIVED={
    'entity_resolution_review':'Entity Resolution Review',
    'acquisition_run':'Acquisition Runs',
    'content_segment':'Content Segments',
    'content_topic':'Content-Topic Links',
    'opinion':'Opinions',
    'claim':'Claims',
    'entity_mention':'Entity Mentions',
    'claim_entity':'Claim-Entity Links',
    'emerging_topic':'Emerging Topics',
    'verification_claim':'Verification Claims',
    'claim_evidence_link':'Claim-Evidence Links',
    'evidence_cluster':'Evidence Clusters',
    'evidence_search_run':'Evidence Search Runs',
    'evidence_candidate_url':'Evidence Candidate URLs',
    'acquisition_job':'Acquisition Jobs',
    'acquisition_run_log':'Acquisition Run Log',
    'source_run_state':'Source Run State',
    'acquisition_campaign':'Acquisition Campaigns',
    'acquisition_campaign_source':'Campaign Sources',
}

CATEGORY_ORDER=['Transactional Data','Master & Reference Data','Technical / Derived Data']
CATEGORY_TABLES={
    'Transactional Data':TRANSACTIONAL,
    'Master & Reference Data':MASTER_REFERENCE,
    'Technical / Derived Data':TECHNICAL_DERIVED,
}
SAFE_TABLES=set().union(*[set(x.keys()) for x in CATEGORY_TABLES.values()])


def _present_tables(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _table_count(con,table):
    return int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _columns(con,table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]


def table_catalog(con):
    present=_present_tables(con)
    rows=[]
    for category in CATEGORY_ORDER:
        mapping=CATEGORY_TABLES[category]
        for table,label in mapping.items():
            if table not in present:
                continue
            rows.append({
                'category':category,
                'table':table,
                'label':label,
                'count':_table_count(con,table),
                'columns':_columns(con,table),
            })
    # Preserve visibility of unknown tables, but keep them out of primary user groups.
    known={x['table'] for x in rows}
    for table in sorted(present-known):
        if table.startswith('sqlite_'):
            continue
        rows.append({
            'category':'Technical / Derived Data',
            'table':table,
            'label':table.replace('_',' ').title(),
            'count':_table_count(con,table),
            'columns':_columns(con,table),
        })
        SAFE_TABLES.add(table)
    return rows


def browse_table(con,table,limit=100,offset=0,search=None):
    present=_present_tables(con)
    if table not in present:
        raise ValueError('Table does not exist in this repository.')
    # Only allow actual repository tables; identifiers are validated against sqlite metadata.
    cols=_columns(con,table)
    lim=max(1,min(int(limit),500)); off=max(0,int(offset))
    where=''; params=[]
    if search:
        textcols=[]
        for r in con.execute(f'PRAGMA table_info("{table}")').fetchall():
            typ=(r[2] or '').upper()
            if 'CHAR' in typ or 'TEXT' in typ or not typ:
                textcols.append(r[1])
        if textcols:
            where=' WHERE '+' OR '.join([f'CAST("{c}" AS TEXT) LIKE ?' for c in textcols])
            params=[f'%{search}%']*len(textcols)
    total=int(con.execute(f'SELECT COUNT(*) FROM "{table}"'+where,params).fetchone()[0])
    rs=con.execute(f'SELECT * FROM "{table}"'+where+f' LIMIT ? OFFSET ?',(*params,lim,off)).fetchall()
    rows=[]
    for r in rs:
        d=dict(r)
        for k,v in list(d.items()):
            if isinstance(v,str) and len(v)>4000:
                d[k]=v[:4000]+'…'
        rows.append(d)
    return {'table':table,'columns':cols,'total':total,'limit':lim,'offset':off,'rows':rows}


def repository_overview(con,profile_id):
    cat=table_catalog(con)
    grouped=[]
    for category in CATEGORY_ORDER:
        items=[x for x in cat if x['category']==category]
        if items:
            grouped.append({
                'category':category,
                'table_count':len(items),
                'record_count':sum(x['count'] for x in items),
                'tables':items,
            })
    return {
        'profile_id':profile_id,
        'groups':grouped,
        'tables':cat,
        'table_count':len(cat),
        'record_count':sum(x['count'] for x in cat),
    }


def _industry_label(raw):
    s=(raw or '').strip()
    low=s.lower()
    if low in {'cafe','coffee','coffee shop','coffee shops'}:
        return 'Coffee'
    if low in {'electrical appliances','electrical appliance','appliances','home appliances'}:
        return 'Electrical Appliances'
    if low in {'it retail','electronics','electronics retail','consumer electronics'}:
        return 'IT & Electronics Retail'
    return s or 'Unspecified'


def _coverage_query(con,sql,params=()):
    return [dict(r) for r in con.execute(sql,params).fetchall()]


def data_coverage(con):
    """Summarize acquired records by industry and analytical use.

    Counts come from stored repository rows only. No estimates or demo values are produced.
    """
    present=_present_tables(con)
    if 'business' not in present:
        return {'rows':[],'note':'Business master table is not available, so industry coverage cannot be calculated.'}

    rows=[]
    specs=[]
    if 'promotion' in present:
        specs.append(('Promotions','promotion','''
            SELECT COALESCE(b.sector,'Unspecified') AS industry,
                   COUNT(*) AS records,
                   COUNT(DISTINCT p.business_id) AS companies,
                   MIN(COALESCE(NULLIF(p.published_at,''),p.first_seen_at)) AS date_from,
                   MAX(COALESCE(NULLIF(p.published_at,''),p.last_seen_at)) AS date_to
            FROM promotion p JOIN business b ON b.business_id=p.business_id
            GROUP BY COALESCE(b.sector,'Unspecified')
        '''))
    if 'price_version' in present and 'listing' in present:
        specs.append(('Price Comparison','price_version','''
            SELECT COALESCE(b.sector,'Unspecified') AS industry,
                   COUNT(*) AS records,
                   COUNT(DISTINCT l.business_id) AS companies,
                   MIN(p.first_seen_at) AS date_from,
                   MAX(p.last_seen_at) AS date_to
            FROM price_version p
            JOIN listing l ON l.listing_id=p.listing_id
            JOIN business b ON b.business_id=l.business_id
            GROUP BY COALESCE(b.sector,'Unspecified')
        '''))
    if 'listing' in present:
        specs.append(('Product & Service Comparison','listing','''
            SELECT COALESCE(b.sector,'Unspecified') AS industry,
                   COUNT(*) AS records,
                   COUNT(DISTINCT l.business_id) AS companies,
                   MIN(l.first_seen_at) AS date_from,
                   MAX(l.last_seen_at) AS date_to
            FROM listing l JOIN business b ON b.business_id=l.business_id
            GROUP BY COALESCE(b.sector,'Unspecified')
        '''))
    if 'marketplace_signal' in present and 'canonical_product' in present:
        # Marketplace signals do not always carry business_id. Company coverage is therefore not asserted.
        specs.append(('Market Signals','marketplace_signal','''
            SELECT 'Marketplace' AS industry,
                   COUNT(*) AS records,
                   NULL AS companies,
                   MIN(observed_at) AS date_from,
                   MAX(observed_at) AS date_to
            FROM marketplace_signal
        '''))

    for analytical_use,table,sql in specs:
        for r in _coverage_query(con,sql):
            rec=int(r.get('records') or 0)
            if rec<=0:
                continue
            rows.append({
                'industry':_industry_label(r.get('industry')),
                'industry_raw':r.get('industry') or 'Unspecified',
                'analytical_use':analytical_use,
                'companies':None if r.get('companies') is None else int(r.get('companies') or 0),
                'records':rec,
                'date_from':r.get('date_from'),
                'date_to':r.get('date_to'),
                'sample_table':table,
            })
    rows.sort(key=lambda x:(x['industry'],x['analytical_use']))
    return {
        'rows':rows,
        'industries':sorted({x['industry'] for x in rows}),
        'analytical_uses':sorted({x['analytical_use'] for x in rows}),
        'note':'Coverage is calculated from rows currently stored in the connected repository. Company counts use distinct business IDs where that relationship exists.',
    }


def coverage_sample(con,analytical_use,industry_raw,limit=25,offset=0):
    """Return representative rows for one coverage cell, filtered to its industry."""
    present=_present_tables(con); lim=max(1,min(int(limit),100)); off=max(0,int(offset))
    use=(analytical_use or '').strip(); industry=(industry_raw or 'Unspecified').strip()
    params=[]
    where_sector="COALESCE(b.sector,'Unspecified')=?"
    if use=='Promotions' and {'promotion','business'} <= present:
        base=f''' FROM promotion p JOIN business b ON b.business_id=p.business_id WHERE {where_sector}'''
        params=[industry]
        cols=['business_name','sector','campaign_name','promotion_type','description','valid_from','valid_to','published_at','first_seen_at','last_seen_at','current']
        select='''SELECT b.name AS business_name,b.sector,p.campaign_name,p.promotion_type,p.description,p.valid_from,p.valid_to,p.published_at,p.first_seen_at,p.last_seen_at,p.current'''
    elif use=='Price Comparison' and {'price_version','listing','business'} <= present:
        base=f''' FROM price_version p JOIN listing l ON l.listing_id=p.listing_id JOIN business b ON b.business_id=l.business_id WHERE {where_sector}'''
        params=[industry]
        cols=['business_name','sector','product_or_service','platform','price_type','price','currency','regular_price','promo_price','member_price','promotion_mechanic','valid_from','valid_to','first_seen_at','last_seen_at','current']
        select='''SELECT b.name AS business_name,b.sector,l.raw_name AS product_or_service,l.platform,p.price_type,p.price,p.currency,p.regular_price,p.promo_price,p.member_price,p.promotion_mechanic,p.valid_from,p.valid_to,p.first_seen_at,p.last_seen_at,p.current'''
    elif use=='Product & Service Comparison' and {'listing','business'} <= present:
        base=f''' FROM listing l JOIN business b ON b.business_id=l.business_id WHERE {where_sector}'''
        params=[industry]
        cols=['business_name','sector','product_or_service','platform','seller_name','raw_sku','variant_text','source_url','first_seen_at','last_seen_at','active']
        select='''SELECT b.name AS business_name,b.sector,l.raw_name AS product_or_service,l.platform,l.seller_name,l.raw_sku,l.variant_text,l.source_url,l.first_seen_at,l.last_seen_at,l.active'''
    elif use=='Market Signals' and 'marketplace_signal' in present:
        base=' FROM marketplace_signal'
        params=[]
        cols=['platform','listing_url','price','currency','sold_display','sold_lower_bound','sold_exact','rating','review_count','rank_value','bestseller_flag','flash_sale','observed_at']
        select='''SELECT platform,listing_url,price,currency,sold_display,sold_lower_bound,sold_exact,rating,review_count,rank_value,bestseller_flag,flash_sale,observed_at'''
    else:
        raise ValueError('Coverage group is not available in this repository.')
    total=int(con.execute('SELECT COUNT(*)'+base,params).fetchone()[0])
    rs=con.execute(select+base+' LIMIT ? OFFSET ?',(*params,lim,off)).fetchall()
    return {'analytical_use':use,'industry_raw':industry,'columns':cols,'total':total,'limit':lim,'offset':off,'rows':[dict(r) for r in rs]}


def business_coverage(con,industry_raw=None):
    """Business-level coverage from stored repository rows only."""
    present=_present_tables(con)
    if 'business' not in present:
        return {'rows':[],'note':'Business master table is not available.'}
    where=" WHERE COALESCE(b.sector,'Unspecified')=?" if industry_raw else ''
    params=[industry_raw] if industry_raw else []
    sql=f'''SELECT b.business_id,b.name AS business_name,COALESCE(b.sector,'Unspecified') AS industry_raw,
      {"(SELECT COUNT(*) FROM listing l WHERE l.business_id=b.business_id)" if 'listing' in present else '0'} AS listings,
      {"(SELECT COUNT(*) FROM price_version pv JOIN listing l2 ON l2.listing_id=pv.listing_id WHERE l2.business_id=b.business_id)" if {'price_version','listing'} <= present else '0'} AS prices,
      {"(SELECT COUNT(*) FROM promotion p WHERE p.business_id=b.business_id)" if 'promotion' in present else '0'} AS promotions,
      {"(SELECT MIN(x.d) FROM (SELECT l3.first_seen_at d FROM listing l3 WHERE l3.business_id=b.business_id UNION ALL SELECT p2.first_seen_at d FROM promotion p2 WHERE p2.business_id=b.business_id) x)" if {'listing','promotion'} <= present else 'NULL'} AS date_from,
      {"(SELECT MAX(x.d) FROM (SELECT l4.last_seen_at d FROM listing l4 WHERE l4.business_id=b.business_id UNION ALL SELECT p3.last_seen_at d FROM promotion p3 WHERE p3.business_id=b.business_id) x)" if {'listing','promotion'} <= present else 'NULL'} AS date_to
      FROM business b{where} ORDER BY b.name'''
    rows=[]
    for r in con.execute(sql,params).fetchall():
        d=dict(r); d['industry']=_industry_label(d['industry_raw']); d['total_records']=int(d['listings'] or 0)+int(d['prices'] or 0)+int(d['promotions'] or 0)
        if d['total_records']>0: rows.append(d)
    return {'rows':rows,'note':'Counts use stored Listings, Price History and Promotions. Businesses with no acquired rows are omitted.'}


def business_sample(con,business_id,data_type,limit=25,offset=0):
    present=_present_tables(con); lim=max(1,min(int(limit),100)); off=max(0,int(offset)); typ=(data_type or '').lower()
    if typ=='promotions' and {'promotion','business'}<=present:
        select='SELECT b.name AS business_name,p.campaign_name,p.promotion_type,p.description,p.valid_from,p.valid_to,p.published_at,p.first_seen_at,p.last_seen_at,p.current'; base=' FROM promotion p JOIN business b ON b.business_id=p.business_id WHERE p.business_id=?'; cols=['business_name','campaign_name','promotion_type','description','valid_from','valid_to','published_at','first_seen_at','last_seen_at','current']
    elif typ=='prices' and {'price_version','listing','business'}<=present:
        select='SELECT b.name AS business_name,l.raw_name AS product_or_service,l.platform,p.price_type,p.price,p.currency,p.regular_price,p.promo_price,p.member_price,p.promotion_mechanic,p.valid_from,p.valid_to,p.first_seen_at,p.last_seen_at,p.current'; base=' FROM price_version p JOIN listing l ON l.listing_id=p.listing_id JOIN business b ON b.business_id=l.business_id WHERE l.business_id=?'; cols=['business_name','product_or_service','platform','price_type','price','currency','regular_price','promo_price','member_price','promotion_mechanic','valid_from','valid_to','first_seen_at','last_seen_at','current']
    elif typ=='listings' and {'listing','business'}<=present:
        select='SELECT b.name AS business_name,l.raw_name AS product_or_service,l.platform,l.seller_name,l.raw_sku,l.variant_text,l.source_url,l.first_seen_at,l.last_seen_at,l.active'; base=' FROM listing l JOIN business b ON b.business_id=l.business_id WHERE l.business_id=?'; cols=['business_name','product_or_service','platform','seller_name','raw_sku','variant_text','source_url','first_seen_at','last_seen_at','active']
    else: raise ValueError('Business data group is not available in this repository.')
    total=int(con.execute('SELECT COUNT(*)'+base,[business_id]).fetchone()[0]); rs=con.execute(select+base+' LIMIT ? OFFSET ?',(business_id,lim,off)).fetchall()
    return {'business_id':business_id,'data_type':typ,'columns':cols,'total':total,'limit':lim,'offset':off,'rows':[dict(r) for r in rs]}
