const assert=require('assert');
const FE=require('../src/fe-executor.js');

const rows=[
  {Birth_Year:'1980',Income:'0',MntWines:'10',MntMeatProducts:'20',Dt_Customer:'2020-01-01',Channel:'Rare'},
  {Birth_Year:'1990',Income:'99',MntWines:'30',MntMeatProducts:'40',Dt_Customer:'2021-01-01',Channel:'Web'},
  {Birth_Year:'',Income:'',MntWines:'',MntMeatProducts:'40',Dt_Customer:'',Channel:'Web'}
];
const recommendations=[
  {id:'fe_1',source_fields:['Birth_Year'],output_field:'Age',operation:'reference_year_minus',parameters:{reference_year:2026},reason:'age',basis:['field_semantics'],confidence:.95},
  {id:'fe_2',source_fields:['Income'],output_field:'Income_log1p',operation:'log1p',parameters:{},reason:'skew',basis:['distribution_profile'],confidence:.9},
  {id:'fe_3',source_fields:['MntWines','MntMeatProducts'],output_field:'Total_Spend',operation:'row_sum',parameters:{},reason:'aggregate',basis:['domain_knowledge'],confidence:.8},
  {id:'fe_4',source_fields:['Dt_Customer'],output_field:'Tenure_Days',operation:'date_difference',parameters:{reference_date:'2026-01-01',direction:'reference_minus_source'},reason:'tenure',basis:['temporal_profile'],confidence:.8},
  {id:'fe_5',source_fields:['Dt_Customer'],output_field:'Join_Month',operation:'extract_month',parameters:{},reason:'month',basis:['temporal_profile'],confidence:.7},
  {id:'fe_6',source_fields:['Channel'],output_field:'Channel_Grouped',operation:'group_rare_categories',parameters:{rare_threshold_pct:34,replacement:'Other'},reason:'rare',basis:['frequency_profile'],confidence:.7},
  {id:'fe_7',source_fields:['MntWines','MntMeatProducts'],output_field:'Spend_Interaction',operation:'product',parameters:{},reason:'interaction',basis:['validated_policy'],confidence:.78}
];
const plan={preparation:{featureEngineering:{status:'ready',reviewed:true,recommendations,selectedIds:recommendations.map(x=>x.id)}}};
const matrix=FE.buildAnalyticalDataset({rows,plan,baseColumns:['Income','MntWines','MntMeatProducts']});
assert(matrix.columns.includes('Age'));
assert(matrix.columns.includes('Income_log1p'));
assert(matrix.columns.includes('Total_Spend'));
assert(matrix.columns.includes('Spend_Interaction'));
assert.equal(matrix.rows[0].Age,46);
assert.equal(matrix.rows[1].Age,36);
assert.equal(matrix.rows[2].Age,'');
assert.equal(matrix.rows[0].Income_log1p,0);
assert(Math.abs(matrix.rows[1].Income_log1p-Math.log1p(99))<1e-12);
assert.equal(matrix.rows[0].Total_Spend,30);
assert.equal(matrix.rows[2].Total_Spend,'','row_sum must not silently turn partial missing components into a lower total');
assert.equal(matrix.rows[0].Spend_Interaction,200);
assert.equal(matrix.rows[2].Spend_Interaction,'','product must preserve missingness when any source component is missing');
assert.equal(matrix.rows[0].Join_Month,1);
assert.equal(matrix.rows[0].Channel_Grouped,'Other');
assert.equal(matrix.rows[1].Channel_Grouped,'Web');
assert.equal(matrix.manifest.reviewed,true);
assert.equal(matrix.manifest.review_status,'ready');
assert.equal(matrix.manifest.applied,true);
assert.equal(matrix.lineage.length,7);
assert(matrix.lineage.every(x=>x.executed_by==='browser'));
assert(matrix.lineage.every(x=>x.recommended_by==='KU Analytical Intelligence'));

const collisionPlan={preparation:{featureEngineering:{status:'ready',reviewed:true,recommendations:[recommendations[0]],selectedIds:['fe_1']}}};
const collision=FE.compilePlan({plan:collisionPlan,baseColumns:['Age','Birth_Year']});
assert.equal(collision.derived_fields[0],'Age_FE');

const unreviewed={preparation:{featureEngineering:{status:'ready',reviewed:false,recommendations,selectedIds:['fe_1']}}};
assert.equal(FE.buildAnalyticalDataset({rows,plan:unreviewed,baseColumns:['Income']}).lineage.length,0);

const reviewedNone={preparation:{featureEngineering:{status:'ready',reviewed:true,recommendations,selectedIds:[]}}};
const emptyMatrix=FE.buildAnalyticalDataset({rows,plan:reviewedNone,baseColumns:['Income']});
assert.equal(emptyMatrix.manifest.reviewed,true);
assert.equal(emptyMatrix.manifest.applied,false);
assert.deepStrictEqual(emptyMatrix.manifest.derived_fields,[]);
console.log('[Feature Engineering Executor smoke completed]');
