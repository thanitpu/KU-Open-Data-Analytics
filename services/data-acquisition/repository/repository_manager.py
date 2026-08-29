from pathlib import Path
from datetime import datetime
import json,sqlite3
from repository_engine import SCHEMA_VERSION,connect
ROOT=Path(__file__).resolve().parents[1];CONFIG=ROOT/"config/repository_config.json"
def _read():
    if not CONFIG.exists():return {"active_repository_path":"","repositories":[]}
    try:return json.loads(CONFIG.read_text(encoding="utf-8"))
    except:return {"active_repository_path":"","repositories":[]}
def _write(x):CONFIG.parent.mkdir(parents=True,exist_ok=True);CONFIG.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
def register(path,name=None):
    p=Path(path).expanduser().resolve();cfg=_read();repos=cfg.setdefault("repositories",[])
    item={"name":name or p.stem,"path":str(p),"last_used_at":datetime.now().isoformat()}
    old=next((x for x in repos if x.get("path")==str(p)),None)
    old.update(item) if old else repos.append(item);cfg["active_repository_path"]=str(p);_write(cfg);return cfg
def create_repository(path,name=None):
    p=Path(path).expanduser().resolve()
    if p.suffix.lower() not in (".sqlite3",".sqlite",".db"):p=p/"ku2d_repository.sqlite3"
    con=connect(p,create=True);con.close();register(p,name);return status()
def select_repository(path,name=None):
    p=Path(path).expanduser().resolve()
    if not p.exists():raise FileNotFoundError(str(p))
    con=sqlite3.connect(p)
    try:
        tables={x[0] for x in con.execute("select name from sqlite_master where type='table'")}
        if "schema_meta" not in tables:raise ValueError("Not a recognized KU2D repository.")
    finally:con.close()
    register(p,name);return status()
def status():
    cfg=_read();raw=cfg.get("active_repository_path","")
    if not raw:return {"configured":False,"exists":False,"path":"","status":"not-configured","repositories":cfg.get("repositories",[])}
    p=Path(raw);out={"configured":True,"exists":p.exists(),"path":str(p),"status":"connected" if p.exists() else "missing","repositories":cfg.get("repositories",[])}
    if p.exists():
        try:
            con=sqlite3.connect(p);con.row_factory=sqlite3.Row
            vs=[x["schema_version"] for x in con.execute("select schema_version from schema_meta order by applied_at")]
            con.close();out.update(schema_versions=vs,compatible=SCHEMA_VERSION in vs,size_bytes=p.stat().st_size)
        except Exception as e:out.update(status="invalid",compatible=False,error=str(e))
    return out
def health_check():
    st=status()
    if not st["exists"]:return {**st,"integrity":"not-checked"}
    con=sqlite3.connect(st["path"])
    try:return {**st,"integrity":con.execute("pragma integrity_check").fetchone()[0],"foreign_key_issues":len(con.execute("pragma foreign_key_check").fetchall())}
    finally:con.close()
def backup():
    st=status()
    if not st["exists"]:raise FileNotFoundError(st.get("path") or "No repository")
    p=Path(st["path"]);target=p.with_name(f"{p.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{p.suffix}")
    a=sqlite3.connect(p);b=sqlite3.connect(target)
    try:a.backup(b)
    finally:a.close();b.close()
    return {"ok":True,"backup_path":str(target)}
def compatibility():
    st=status()
    if not st["exists"]:return {"ok":False,"action":"locate-or-create",**st}
    if st.get("compatible"):return {"ok":True,"action":"none","schema_version":SCHEMA_VERSION}
    return {"ok":False,"action":"migration-required","message":"Undefined migration blocked; backup and migration definition required."}
