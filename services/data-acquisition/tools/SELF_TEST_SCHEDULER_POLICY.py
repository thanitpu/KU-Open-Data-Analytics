from datetime import datetime,timezone,timedelta
from control_plane.lifecycle_policy import evaluate_source

now=datetime.now(timezone.utc)
source={'enabled':True}
q={'audit_passed':1,'approved_for_store':1,'last_audit_at':now.isoformat()}
assert evaluate_source(source=source,quality=q,run_state={},now=now)['action']=='scheduled-acquire'
assert evaluate_source(source=source,quality={**q,'audit_passed':0},run_state={},now=now)['action']=='deep-audit'
assert evaluate_source(source=source,quality=q,run_state={'consecutive_failures':3},now=now)['action']=='re-explore'
old=(now-timedelta(days=31)).isoformat()
assert evaluate_source(source=source,quality={**q,'last_audit_at':old},run_state={},now=now)['action']=='deep-audit'
assert evaluate_source(source=source,quality=q,run_state={},assigned_fingerprint='new',audited_fingerprint='old',now=now)['action']=='deep-audit'
print('Scheduler policy: PASS')
