import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/'config'/'acquisition_access_policies.json'
def policies():return json.loads(CFG.read_text(encoding='utf-8'))
def policy(level):
    x=policies();return dict(x['levels'].get(str(int(level or 0)),{'min_delay_seconds':5,'max_pages_per_run':5,'max_retries':0,'default_cadence':'manual','continuous_allowed':False}))
