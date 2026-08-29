from __future__ import annotations
import os
from typing import Any
from .observation_store import ObservationStore


def _store():
    return ObservationStore()


def entity_key(record:dict[str,Any]) -> str|None:
    rt=record.get('record_type')
    if rt=='ProductCandidate':
        return str(record.get('sku') or record.get('product_id') or record.get('source_url') or record.get('product_name') or '') or None
    if rt in {'PromotionCandidate','PromotionListingItemCandidate'}:
        return str(record.get('promotion_id') or record.get('source_url') or record.get('promotion_title') or '') or None
    return str(record.get('source_url') or record.get('title') or '') or None


def persist_records(*, source_id:str, source_url:str, lifecycle_stage:str, records:list[dict],
                    validation_status:str, technique:str|None=None, profile_fingerprint:str|None=None,
                    rejected_reason:str|None=None) -> dict:
    if not records:return {'stored':0,'status':validation_status}
    st=_store(); n=0
    for r in records:
        if not isinstance(r,dict):continue
        st.add_observation(source_id=source_id,source_url=r.get('source_url') or source_url,
            lifecycle_stage=lifecycle_stage,record_type=r.get('record_type') or 'UnknownCandidate',payload=r,
            validation_status=validation_status,entity_key=entity_key(r),technique=technique or r.get('technique'),
            profile_fingerprint=profile_fingerprint,rejection_reason=rejected_reason)
        n+=1
    return {'stored':n,'status':validation_status,'path':str(st.path)}


def persist_explore(source_id:str, source_url:str, result:dict) -> dict:
    records=[]
    for tr in result.get('technique_results') or []:
        tech=tr.get('technique')
        for r in tr.get('sample_records') or []:
            if isinstance(r,dict):
                rr=dict(r); rr.setdefault('technique',tech); records.append(rr)
    return persist_records(source_id=source_id,source_url=source_url,lifecycle_stage='explore',records=records,validation_status='exploratory')


def persist_audit(source_id:str, source_url:str, audit:dict) -> dict:
    fp=((audit.get('technique_profile') or {}).get('fingerprint'))
    records=audit.get('sample_records') or []
    status='accepted' if audit.get('audit_passed') else 'exploratory'
    return persist_records(source_id=source_id,source_url=source_url,lifecycle_stage='deep-audit',records=records,validation_status=status,profile_fingerprint=fp)


def persist_acquire(source_id:str, source_url:str, records:list[dict], profile_fingerprint:str|None=None) -> dict:
    return persist_records(source_id=source_id,source_url=source_url,lifecycle_stage='acquire',records=records,validation_status='trusted',profile_fingerprint=profile_fingerprint)
