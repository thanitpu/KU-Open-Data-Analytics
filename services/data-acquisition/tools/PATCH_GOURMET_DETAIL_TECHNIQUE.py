from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = ROOT / 'acquisition' / 'technique_strategy.py'
AUDIT = ROOT / 'acquisition' / 'deep_audit.py'


def ensure_replace(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f'Patch anchor not found: {label}')
    return text.replace(old, new, 1)


s = STRATEGY.read_text(encoding='utf-8')

s = ensure_replace(
    s,
    "    gourmet_graphql_catalog,gourmet_rendered_catalog,gourmet_promotion_surface,gourmet_catalog_network)\n",
    "    gourmet_graphql_catalog,gourmet_rendered_catalog,gourmet_promotion_surface,gourmet_catalog_network)\nfrom gourmet_detail_technique import gourmet_product_detail_catalog\n",
    'detail import',
)

s = ensure_replace(
    s,
    " {\"key\":\"gourmet_graphql_catalog\",\"label\":\"Gourmet Market GraphQL Product Catalog\",\"kind\":\"content\"},\n {\"key\":\"gourmet_rendered_catalog\",\"label\":\"Gourmet Market Rendered Product Cards\",\"kind\":\"content\"},",
    " {\"key\":\"gourmet_graphql_catalog\",\"label\":\"Gourmet Market GraphQL Product Catalog\",\"kind\":\"content\"},\n {\"key\":\"gourmet_product_detail_catalog\",\"label\":\"Gourmet Market Official Product Detail Catalog\",\"kind\":\"content\"},\n {\"key\":\"gourmet_rendered_catalog\",\"label\":\"Gourmet Market Rendered Product Cards\",\"kind\":\"content\"},",
    'Gourmet technique catalog',
)

s = ensure_replace(
    s,
    "      'gourmet_graphql_catalog':lambda: _special_result('gourmet_graphql_catalog','Gourmet Market GraphQL Product Catalog',gourmet_graphql_catalog(url,max_pages)),\n      'gourmet_rendered_catalog':lambda: _special_result('gourmet_rendered_catalog','Gourmet Market Rendered Product Cards',gourmet_rendered_catalog(url,max_pages)),",
    "      'gourmet_graphql_catalog':lambda: _special_result('gourmet_graphql_catalog','Gourmet Market GraphQL Product Catalog',gourmet_graphql_catalog(url,max_pages)),\n      'gourmet_product_detail_catalog':lambda: _special_result('gourmet_product_detail_catalog','Gourmet Market Official Product Detail Catalog',gourmet_product_detail_catalog(url,max_pages)),\n      'gourmet_rendered_catalog':lambda: _special_result('gourmet_rendered_catalog','Gourmet Market Rendered Product Cards',gourmet_rendered_catalog(url,max_pages)),",
    'Explore execution mapping',
)

s = ensure_replace(
    s,
    "        if key not in ('bigc_product_catalog','bigc_catalog_network','makro_pro_catalog','makro_pro_network','tops_product_catalog','tops_campaign_catalog','tops_catalog_network','gourmet_graphql_catalog','gourmet_rendered_catalog','gourmet_catalog_network') and z.get('identity_pct',0)<75:continue",
    "        if key not in ('bigc_product_catalog','bigc_catalog_network','makro_pro_catalog','makro_pro_network','tops_product_catalog','tops_campaign_catalog','tops_catalog_network','gourmet_graphql_catalog','gourmet_product_detail_catalog','gourmet_rendered_catalog','gourmet_catalog_network') and z.get('identity_pct',0)<75:continue",
    'Product identity allowlist',
)

s = ensure_replace(
    s,
    "            if key=='gourmet_graphql_catalog':score+=60\n            elif key=='gourmet_rendered_catalog':score+=32",
    "            if key=='gourmet_graphql_catalog':score+=60\n            elif key=='gourmet_product_detail_catalog':score+=48\n            elif key=='gourmet_rendered_catalog':score+=32",
    'Gourmet ranking bonus',
)

s = ensure_replace(
    s,
    "        if 'gourmet_rendered_catalog' in tset:\n            cfg=_assignment_operational_config(assignment_rows,'gourmet_rendered_catalog')",
    "        if 'gourmet_product_detail_catalog' in tset:\n            cfg=_assignment_operational_config(assignment_rows,'gourmet_product_detail_catalog')\n            x=gourmet_product_detail_catalog(url,max_pages=max_pages,source_id=source.get('source_id'),progressive=True,operational_config=cfg,stable_sample=stable_sample)\n            rr=x.get('rows') or [];rows.extend(rr)\n            results.append(_tech_result('gourmet_product_detail_catalog','Gourmet Market Official Product Detail Catalog',rr,len(x.get('urls_checked') or []),x.get('urls_checked') or [],x.get('potential') or {},x.get('diagnostics') or []))\n        if 'gourmet_rendered_catalog' in tset:\n            cfg=_assignment_operational_config(assignment_rows,'gourmet_rendered_catalog')",
    'Operational materialization',
)

s = ensure_replace(
    s,
    "        handled={'gourmet_graphql_catalog','gourmet_rendered_catalog','gourmet_promotion_surface','gourmet_catalog_network','generic_sitemap'}",
    "        handled={'gourmet_graphql_catalog','gourmet_product_detail_catalog','gourmet_rendered_catalog','gourmet_promotion_surface','gourmet_catalog_network','generic_sitemap'}",
    'Operational handled set',
)

s = ensure_replace(
    s,
    "'graphql_endpoint','graphql_operation','graphql_query_hash','identity_source') if op.get(k) is not None}",
    "'graphql_endpoint','graphql_operation','graphql_query_hash','identity_source','seed_urls','crawl_mode') if op.get(k) is not None}",
    'Technique fingerprint operational fields',
)

STRATEGY.write_text(s, encoding='utf-8')

a = AUDIT.read_text(encoding='utf-8')
a = ensure_replace(
    a,
    "      'gourmet-graphql-product','gourmet-rendered-product-card'}",
    "      'gourmet-graphql-product','gourmet-product-detail','gourmet-rendered-product-card'}",
    'Deep Audit Gourmet provenance',
)
AUDIT.write_text(a, encoding='utf-8')

# Fail immediately if the integrated contract is incomplete.
assert 'gourmet_product_detail_catalog' in STRATEGY.read_text(encoding='utf-8')
assert 'gourmet-product-detail' in AUDIT.read_text(encoding='utf-8')
print('Gourmet product-detail integration patch: PASS')
