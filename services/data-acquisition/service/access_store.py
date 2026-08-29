from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data'/'acquisition_service.sqlite3'

def now(): return datetime.now(timezone.utc).isoformat()
def con():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=con(); c.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS customer(
      customer_id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS study_request(
      request_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customer(customer_id),question TEXT NOT NULL,
      scope_json TEXT,status TEXT NOT NULL DEFAULT 'draft',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS data_product(
      product_id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT,purpose TEXT,base_monthly_fee REAL NOT NULL DEFAULT 0,
      estimated_monthly_cost REAL NOT NULL DEFAULT 0,shareable INTEGER NOT NULL DEFAULT 1,
      coverage_start TEXT,coverage_end TEXT,status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS product_source(
      product_id TEXT NOT NULL REFERENCES data_product(product_id),source_id TEXT NOT NULL,role TEXT,
      PRIMARY KEY(product_id,source_id));
    CREATE TABLE IF NOT EXISTS entitlement(
      entitlement_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customer(customer_id),
      product_id TEXT NOT NULL REFERENCES data_product(product_id),access_start TEXT,access_end TEXT,
      historical_from TEXT,historical_to TEXT,ongoing_access INTEGER NOT NULL DEFAULT 1,
      download_allowed INTEGER NOT NULL DEFAULT 1,q2d_allowed INTEGER NOT NULL DEFAULT 1,
      field_scope_json TEXT,source_scope_json TEXT,pricing_rule TEXT NOT NULL DEFAULT 'standard',
      status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS credit_ledger(
      credit_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customer(customer_id),product_id TEXT,
      amount REAL NOT NULL,reason TEXT,created_at TEXT NOT NULL);
    ''')
    n=c.execute('select count(*) n from customer').fetchone()['n']
    if not n:
        t=now()
        c.executemany('insert into customer(customer_id,name,status,created_at) values(?,?,?,?)',[
          ('CUST-A','Customer A','active',t),('CUST-B','Customer B','active',t)])
        c.execute('''insert into data_product(product_id,name,description,purpose,base_monthly_fee,estimated_monthly_cost,shareable,coverage_start,status,created_at)
          values(?,?,?,?,?,?,?,?,?,?)''',('DP-COMP-001','Competitor Price & Promotion Monitor',
          'Reusable data product for recurring competitor price/promotion observations.','competitive_intelligence',600,300,1,'2026-01-01','active',t))
        c.execute('''insert into entitlement(entitlement_id,customer_id,product_id,access_start,historical_from,ongoing_access,download_allowed,q2d_allowed,pricing_rule,status,created_at)
          values(?,?,?,?,?,?,?,?,?,?,?)''',('ENT-A','CUST-A','DP-COMP-001','2026-01-01','2026-01-01',1,1,1,'originator','active',t))
    c.commit(); c.close()

def rows(sql,args=()):
    c=con(); r=[dict(x) for x in c.execute(sql,args).fetchall()]; c.close(); return r

def customers(): return rows('select * from customer order by name')
def products():
    ps=rows('select * from data_product order by created_at desc')
    for p in ps:
        p['active_entitlements']=rows('select customer_id,pricing_rule,access_start,historical_from,historical_to,ongoing_access,status from entitlement where product_id=? and status="active"',(p['product_id'],))
    return ps
def entitlements(): return rows('''select e.*,c.name customer_name,p.name product_name from entitlement e join customer c using(customer_id) join data_product p using(product_id) order by e.created_at desc''')
def credits(): return rows('''select l.*,c.name customer_name,p.name product_name from credit_ledger l join customer c using(customer_id) left join data_product p using(product_id) order by l.created_at desc''')

def add_customer(name):
    cid='CUST-'+uuid.uuid4().hex[:8].upper(); c=con(); c.execute('insert into customer values(?,?,?,?)',(cid,name,'active',now())); c.commit(); c.close(); return cid

def add_product(name,description,purpose,base_monthly_fee,estimated_monthly_cost,shareable=True):
    pid='DP-'+uuid.uuid4().hex[:8].upper(); c=con(); c.execute('''insert into data_product(product_id,name,description,purpose,base_monthly_fee,estimated_monthly_cost,shareable,status,created_at) values(?,?,?,?,?,?,?,?,?)''',(pid,name,description,purpose,float(base_monthly_fee),float(estimated_monthly_cost),1 if shareable else 0,'active',now())); c.commit(); c.close(); return pid

def add_entitlement(customer_id,product_id,access_start=None,historical_from=None,historical_to=None,ongoing_access=True,pricing_rule='shared'):
    eid='ENT-'+uuid.uuid4().hex[:10].upper(); c=con(); c.execute('''insert into entitlement(entitlement_id,customer_id,product_id,access_start,historical_from,historical_to,ongoing_access,download_allowed,q2d_allowed,pricing_rule,status,created_at) values(?,?,?,?,?,?,?,?,?,?,?,?)''',(eid,customer_id,product_id,access_start,historical_from,historical_to,1 if ongoing_access else 0,1,1,pricing_rule,'active',now())); c.commit(); c.close(); return eid

def pricing_preview(product_id,joining_customer_id=None,historical_months=0):
    c=con(); p=c.execute('select * from data_product where product_id=?',(product_id,)).fetchone()
    if not p: c.close(); raise KeyError(product_id)
    active=c.execute('select count(*) n from entitlement where product_id=? and status="active" and ongoing_access=1',(product_id,)).fetchone()['n']
    base=float(p['base_monthly_fee']); cost=float(p['estimated_monthly_cost']); after=active+(1 if joining_customer_id else 0)
    shared=round(base*2/3,2) if p['shareable'] and after>=2 else base
    historical=round(base*max(0,int(historical_months)),2)
    ongoing_revenue=round(shared*after,2)
    contribution=round(ongoing_revenue-cost,2)
    originator_credit=round(base-shared,2) if after>=2 else 0
    c.close()
    return {'product_id':product_id,'base_monthly_fee':base,'estimated_monthly_cost':cost,'existing_ongoing_customers':active,
      'customers_after_join':after,'historical_months':int(historical_months),'historical_charge_new_customer':historical,
      'shared_monthly_price_per_customer':shared,'monthly_platform_revenue':ongoing_revenue,'monthly_contribution_before_overhead':contribution,
      'originator_credit_per_month':originator_credit,'rule':'New customer pays full base fee for historical months; when >=2 ongoing customers, each ongoing price is 2/3 base and 1/3 base can be credited to originator under the current concept.'}

def add_credit(customer_id,product_id,amount,reason):
    cid='CR-'+uuid.uuid4().hex[:10].upper(); c=con(); c.execute('insert into credit_ledger values(?,?,?,?,?,?)',(cid,customer_id,product_id,float(amount),reason,now())); c.commit(); c.close(); return cid

def q2d_manifest(product_id,customer_id):
    c=con(); p=c.execute('select * from data_product where product_id=?',(product_id,)).fetchone();
    e=c.execute('''select * from entitlement where product_id=? and customer_id=? and status='active' and q2d_allowed=1 order by created_at desc limit 1''',(product_id,customer_id)).fetchone(); c.close()
    if not p: raise KeyError('product')
    if not e: raise PermissionError('No active Q2D entitlement for this customer/data product')
    return {'schema':'ku2d.data-product-handoff.v0.1','product_id':product_id,'product_name':p['name'],'customer_id':customer_id,
      'access':{'historical_from':e['historical_from'],'historical_to':e['historical_to'],'ongoing_access':bool(e['ongoing_access']),'download_allowed':bool(e['download_allowed']),'q2d_allowed':bool(e['q2d_allowed'])},
      'dataset_state_contract':{'source':'data_product','data_product_id':product_id,'entitlement_id':e['entitlement_id'],'read_only_upstream':True},'generated_at':now()}

init()
