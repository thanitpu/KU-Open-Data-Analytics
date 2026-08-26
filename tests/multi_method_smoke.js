const assert=require('assert');
const M=require('../src/multi-method.js');

assert(Math.abs(M.pearson([1,2,3,4],[2,4,6,8])-1)<1e-12);
assert(Math.abs(M.spearman([1,2,3,4],[8,6,4,2])+1)<1e-12);
assert(M.correlationP(.7,30)<.001);

const regRows=Array.from({length:24},(_,i)=>({Target:5+3*(i+1),X:i+1,X2:2*(i+1)}));
const regMatrix={columns:['Target','X','X2'],rows:regRows};
const regPlan={target:'Target',preparation:{}};
const ols=M.olsResult(regMatrix,regPlan);
assert.equal(ols.status,'COMPLETE');
assert(ols.evidence.r2>.999999999);
assert.equal(ols.evidence.predictors_used,1,'exactly collinear predictor should be screened');
assert.equal(ols.evidence.predictors_dropped,1);
assert(ols.warnings.some(x=>x.includes('collinearity')));

const welchMatrix={columns:['Score','Group'],rows:[
  {Score:10,Group:'A'},{Score:11,Group:'A'},{Score:9,Group:'A'},{Score:12,Group:'A'},
  {Score:30,Group:'B'},{Score:31,Group:'B'},{Score:29,Group:'B'},{Score:32,Group:'B'}
]};
const welch=M.welchResult(welchMatrix,{target:'Score',preparation:{groupField:'Group'}});
assert.equal(welch.evidence.groups,2);
assert(welch.evidence.p_value<.001);
assert(Number.isFinite(welch.evidence.hedges_g));

const anovaMatrix={columns:['Score','Group'],rows:[
  {Score:10,Group:'A'},{Score:11,Group:'A'},{Score:9,Group:'A'},
  {Score:20,Group:'B'},{Score:21,Group:'B'},{Score:19,Group:'B'},
  {Score:30,Group:'C'},{Score:31,Group:'C'},{Score:29,Group:'C'}
]};
const anova=M.anovaResult(anovaMatrix,{target:'Score',preparation:{groupField:'Group'}});
assert.equal(anova.evidence.groups,3);
assert(anova.evidence.p_value<.001);
assert(anova.evidence.eta_squared>.9);

const corr=M.runLocalMethod('pearson-correlation',{columns:['Target','X'],rows:regRows.map(r=>({Target:r.Target,X:r.X}))},{target:'Target',preparation:{}});
assert.equal(corr.evidence.relationships_tested,1);
assert(corr.evidence.strongest_abs_correlation>.999999);

const prepA={groupField:'G',featureEngineering:{status:'ready',reviewed:true,recommenderVersion:'r1',selectedIds:['b','a'],derivedFields:['D'],lineage:[{output_field:'D',source_fields:['B','A'],operation:'row_sum',parameters:{}}]}};
const prepB={groupField:'G',featureEngineering:{status:'ready',reviewed:true,recommenderVersion:'r1',selectedIds:['a','b'],derivedFields:['D'],lineage:[{output_field:'D',source_fields:['A','B'],operation:'row_sum',parameters:{}}]}};
assert.deepStrictEqual(M.preparationSignature(prepA),M.preparationSignature(prepB));

const plan={questionType:'explain-drivers',target:'Target',route:'regression',methodMode:'custom',selectedMethods:['linear-regression'],predictors:['X'],preparation:prepA};
const fields=[{name:'Target',storage:'numeric',level:'Scale'},{name:'X',storage:'numeric',level:'Scale'}];
const snap={questionType:plan.questionType,target:plan.target,route:plan.route,methodMode:plan.methodMode,selectedMethods:['linear-regression'],predictors:['X'],preparation:prepB,datasetRevision:2,fieldMetadata:fields};
const state={analysisPlan:plan,dataset:{revision:2,fields},result:{planSnapshot:snap}};
assert.equal(M.resultMatchesPlan(state),true);
state.analysisPlan={...plan,predictors:['X','Other']};
state.dataset.fields=[...fields,{name:'Other',storage:'numeric',level:'Scale'}];
assert.equal(M.resultMatchesPlan(state),false,'predictor change must make previous result stale');

console.log('[Multi-method statistical smoke completed]');
