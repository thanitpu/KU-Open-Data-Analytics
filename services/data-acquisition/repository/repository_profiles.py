from pathlib import Path
import json, os
ROOT=Path(__file__).resolve().parents[1]
PROFILES=ROOT/"config/repository_profiles.json"

def load_profiles():
    return json.loads(PROFILES.read_text(encoding="utf-8"))

def _resolved(p):
    p=dict(p)
    env=p.get("env_override")
    if env and os.getenv(env," ").strip(): p["path"]=os.getenv(env).strip(); p["path_source"]="environment"
    else: p["path_source"]="configured"
    return p

def active_profile():
    x=load_profiles(); pid=x.get("active_profile")
    return next((_resolved(p) for p in x.get("profiles",[]) if p.get("profile_id")==pid),None)

def set_active(profile_id):
    x=load_profiles()
    if not any(p.get("profile_id")==profile_id for p in x.get("profiles",[])): raise KeyError(profile_id)
    x["active_profile"]=profile_id; PROFILES.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
    return active_profile()

def profile_by_id(profile_id):
    return next((_resolved(p) for p in load_profiles().get("profiles",[]) if p.get("profile_id")==profile_id),None)

def profile_statuses():
    rows=[]
    for raw in load_profiles().get("profiles",[]):
        p=_resolved(raw); path=Path(p.get("path") or "").expanduser()
        rows.append({**p,"exists":path.is_file(),"resolved_path":str(path)})
    return rows
