const assert=require('assert');
const manifest=require('../src/profile-manifest.js');
const headers=['Customer_ID','Income','Education','Signup_Date'];
const data=[
  {Customer_ID:'C001',Income:10,Education:'Graduate',Signup_Date:'2026-01-01'},
  {Customer_ID:'C002',Income:11,Education:'Graduate',Signup_Date:'2026-01-02'},
  {Customer_ID:'C003',Income:12,Education:'Master',Signup_Date:'2026-01-03'},
  {Customer_ID:'C004',Income:13,Education:'Graduate',Signup_Date:'2026-01-04'},
  {Customer_ID:'C005',Income:14,Education:'PhD',Signup_Date:'2026-01-05'},
  {Customer_ID:'C006',Income:15,Education:'Graduate',Signup_Date:'2026-01-06'},
  {Customer_ID:'C007',Income:16,Education:'Master',Signup_Date:'2026-01-07'},
  {Customer_ID:'C008',Income:17,Education:'Graduate',Signup_Date:'2026-01-08'},
  {Customer_ID:'C009',Income:18,Education:'Master',Signup_Date:'2026-01-09'},
  {Customer_ID:'C010',Income:1000,Education:'Graduate',Signup_Date:'2026-01-10'},
];
const out=manifest.build({headers,data,types:{Customer_ID:'text',Income:'numeric',Education:'text',Signup_Date:'text'},meta:{Customer_ID:{level:'Nominal'},Income:{level:'Scale'},Education:{level:'Ordinal'},Signup_Date:{level:'Nominal'}},analysisIntent:{question_type:'predict-outcome',target:'Education',analytical_family:'Multiclass Classification'}});
assert.equal(out.schema_version,'1.0');
assert.equal(out.generated_by,'browser');
assert.equal(out.privacy.row_level_values_included,false);
assert.equal(out.dataset_profile.rows,10);
assert.equal(out.dataset_profile.temporal_fields,1);
const income=out.fields.find(f=>f.name==='Income');
assert(income.distribution.histogram.bins.length>=4);
assert(income.profile.skewness>1);
assert(income.outliers.method_iqr.count>=1);
const education=out.fields.find(f=>f.name==='Education');
assert.equal(education.role,'target');
assert.equal(education.frequency.top[0].value,'Graduate');
const id=out.fields.find(f=>f.name==='Customer_ID');
assert.equal(id.frequency.redacted,true);
assert.equal(id.frequency.top.length,0);
const date=out.fields.find(f=>f.name==='Signup_Date');
assert.equal(date.temporal.detected,true);
assert.equal(date.temporal.granularity,'daily');
const serialized=JSON.stringify(out);
assert(!serialized.includes('C001'),'Identifier values must not be included in the profile manifest');
assert(!Object.prototype.hasOwnProperty.call(out,'data'),'Raw row data must not be attached to the manifest');
console.log('[Profile Manifest smoke completed]');
