from __future__ import annotations
from datetime import datetime, timezone, timedelta


def _dt(value):
    if not value:return None
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return None


def evaluate_source(*, source:dict, quality:dict|None, run_state:dict|None,
                    assigned_fingerprint:str|None=None, audited_fingerprint:str|None=None,
                    now:datetime|None=None, deep_audit_days:int=30,
                    failure_reexplore_threshold:int=3) -> dict:
    """Return the next autonomous lifecycle action without mutating source state."""
    now=now or datetime.now(timezone.utc); quality=quality or {}; run_state=run_state or {}
    if not source.get('enabled',True):
        return {'action':'disabled','reason':'source disabled'}
    if assigned_fingerprint and audited_fingerprint and assigned_fingerprint!=audited_fingerprint:
        return {'action':'deep-audit','reason':'technique profile changed','requires_human_approval':True}
    if not quality.get('audit_passed'):
        return {'action':'deep-audit','reason':'source has no current passing Deep Audit','requires_human_approval':True}
    if not quality.get('approved_for_store'):
        return {'action':'await-human-approval','reason':'Deep Audit passed but profile is not approved','requires_human_approval':True}
    failures=int(run_state.get('consecutive_failures') or 0)
    if failures>=failure_reexplore_threshold:
        return {'action':'re-explore','reason':f'{failures} consecutive acquisition failures','requires_human_approval':False}
    last_audit=_dt(quality.get('last_audit_at'))
    if last_audit and now-last_audit>=timedelta(days=deep_audit_days):
        return {'action':'deep-audit','reason':'periodic Deep Audit due','requires_human_approval':False}
    return {'action':'scheduled-acquire','reason':'approved profile is current','requires_human_approval':False}


def drift_signals(*, records:int|None=None, price_completeness:float|None=None,
                  semantic_quality:float|None=None, repeatability:float|None=None,
                  provenance:float|None=None, blocked_events:int|None=None,
                  schema_changed:bool=False) -> list[dict]:
    out=[]
    if records is not None and records<=0:out.append({'code':'zero-yield','severity':'high'})
    if price_completeness is not None and price_completeness<80:out.append({'code':'price-completeness-low','severity':'high','value':price_completeness})
    if semantic_quality is not None and semantic_quality<80:out.append({'code':'semantic-quality-low','severity':'high','value':semantic_quality})
    if repeatability is not None and repeatability<70:out.append({'code':'repeatability-low','severity':'high','value':repeatability})
    if provenance is not None and provenance<95:out.append({'code':'provenance-low','severity':'high','value':provenance})
    if blocked_events is not None and blocked_events>=2:out.append({'code':'access-blocking-increase','severity':'medium','value':blocked_events})
    if schema_changed:out.append({'code':'schema-changed','severity':'high'})
    return out
