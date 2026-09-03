const assert=require('assert');
const fs=require('fs');
const path=require('path');
const root=path.resolve(__dirname,'..');
const contract=require(path.join(root,'src/ku2d-data-asset.js'));
const fixture=name=>JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/text-analytics',name),'utf8'));

const approved=fixture('ku2d-approved-snapshot.json');
const draft=fixture('ku2d-draft-snapshot.json');
const single=contract.validateAssets(approved);
assert.strictEqual(single.rows.length,approved.record_count);
assert.strictEqual(single.approval.productionApproved,true);
assert.strictEqual(single.rows[0].__ku2d_data_asset_id,approved.data_asset_id);
assert.strictEqual(single.rows[0].__ku2d_record_identity,'r-001');
assert.notStrictEqual(single.rows[0].__ku2d_acquired_at,single.rows[0].__ku2d_effective_at);

const multiple=contract.validateAssets([approved,draft]);
assert.strictEqual(multiple.rows.length,6);
assert.strictEqual(multiple.approval.productionApproved,false,'one draft snapshot must keep the batch non-production-approved');
assert.strictEqual(multiple.rows.filter(row=>row.__ku2d_record_identity==='r-001').length,2,'the same entity may recur in distinct snapshots');
assert.strictEqual(new Set(multiple.rows.filter(row=>row.__ku2d_record_identity==='r-001').map(row=>row.__ku2d_data_asset_id)).size,2);

function rejects(mutator,pattern){const value=fixture('ku2d-approved-snapshot.json');mutator(value);assert.throws(()=>contract.validateAssets(value),pattern);}
rejects(asset=>asset.contract_version='trusted-data-asset-v2',/Unsupported contract_version/);
rejects(asset=>asset.approval_status='pending',/approval_status/);
rejects(asset=>asset.record_count++,/does not match/);
rejects(asset=>asset.records[1].review_id=asset.records[0].review_id,/Duplicate identity/);
rejects(asset=>asset.records[0].review_text=123,/does not match storage_type text/);
rejects(asset=>delete asset.provenance.evidence_refs,/provenance is missing/);
rejects(asset=>asset.acquired_at='2026-08-30',/explicit timezone/);
rejects(asset=>asset.unexpected=true,/unknown fields/);
const incompatible=fixture('ku2d-draft-snapshot.json');incompatible.schema.fields[1].name='review_body';incompatible.records=incompatible.records.map(record=>({review_id:record.review_id,review_body:record.review_text,sentiment_label:record.sentiment_label}));
assert.throws(()=>contract.validateAssets([approved,incompatible]),/incompatible/);
assert.throws(()=>contract.validateAssets([approved,approved]),/Duplicate data_asset_id/);
console.log('KU2D_DATA_ASSET_SMOKE_OK (single + multi snapshot contracts)');
