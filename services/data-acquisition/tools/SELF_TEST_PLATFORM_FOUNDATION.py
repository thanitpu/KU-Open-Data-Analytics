from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime,timezone,timedelta
from control_plane.observation_store import ObservationStore
from control_plane.lifecycle_policy import evaluate_source,drift_signals

with TemporaryDirectory() as td:
    s=ObservationStore(Path(td)/'obs.sqlite3')
    s.add_observation(source_id='SRC-X',source_url='https://example.com/p/1',lifecycle_stage='explore',record_type='ProductCandidate',payload={'sku':'1','price':42},validation_status='exploratory',entity_key='1')
    s.add_observation(source_id='SRC-X',source_url='https://example.com/p/1',lifecycle_stage='acquire',record_type='ProductCandidate',payload={'sku':'1','price':45},validation_status='trusted',entity_key='1')
    s.add_observation(source_id='SRC-X',source_url='https://example.com/',lifecycle_stage='explore',record_type='ProductCandidate',payload={'product_name':'join now','price':1},validation_status='rejected',rejection_reason='marketing_text')
    assert s.summary('SRC-X')['observations']==3
q={'audit_passed':1,'approved_for_store':1,'last_audit_at':datetime.now(timezone.utc).isoformat()}
d=evaluate_source(source={'enabled':True},quality=q,run_state={},assigned_fingerprint='x',audited_fingerprint='x')
assert d['action']=='scheduled-acquire'
d=evaluate_source(source={'enabled':True},quality={**q,'approved_for_store':0},run_state={})
assert d['action']=='await-human-approval'
assert any(x['code']=='price-completeness-low' for x in drift_signals(records=5,price_completeness=70))
print('Platform foundation: PASS')
