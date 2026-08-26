const assert=require('assert');
const profile=require('../src/profile-manifest.js');

const rows=541909;
const headers=['InvoiceNo','Quantity','UnitPrice','Country','CustomerID','Year','Month','Day'];
const data=Array.from({length:rows},(_,i)=>({
  InvoiceNo:`INV${i}`,
  Quantity:(i%20)+1,
  UnitPrice:(i%1000)/10,
  Country:['UK','France','Germany','Spain'][i%4],
  CustomerID:`C${i%5000}`,
  Year:2010+(i%2),
  Month:1+(i%12),
  Day:1+(i%28)
}));
const types={InvoiceNo:'text',Quantity:'numeric',UnitPrice:'numeric',Country:'text',CustomerID:'text',Year:'numeric',Month:'numeric',Day:'numeric'};
const meta=Object.fromEntries(headers.map(h=>[h,{level:['InvoiceNo','Country','CustomerID'].includes(h)?'Nominal':'Scale'}]));
const manifest=profile.build({headers,data,types,meta});

assert.equal(profile.DEFAULT_PROFILE_ROW_LIMIT,100000);
assert.equal(manifest.dataset_profile.rows,rows);
assert.equal(manifest.profile_provenance.mode,'sampled');
assert.equal(manifest.profile_provenance.profile_rows,100000);
assert.equal(manifest.profile_provenance.sampling_method,'deterministic_systematic');
assert.equal(manifest.dataset_profile.duplicate_rows,null);
assert.equal(manifest.dataset_profile.duplicate_rows_basis,'not_computed_large_dataset');
assert.ok(manifest.fields.find(f=>f.name==='Quantity').distribution.histogram.bins.length>0);
assert.ok(manifest.fields.find(f=>f.name==='Quantity').outliers.method_iqr);
assert.ok(manifest.fields.find(f=>f.name==='Country').frequency.top.length>0);
assert.equal(data.length,rows,'full analytical dataset must remain unchanged');

const small=profile.build({headers:['x'],data:[{x:1},{x:2},{x:3}],types:{x:'numeric'},meta:{x:{level:'Scale'}}});
assert.equal(small.profile_provenance.mode,'full');
assert.equal(small.profile_provenance.profile_rows,3);
assert.equal(small.dataset_profile.rows,3);
console.log('[large_dataset_profile_smoke completed]');
