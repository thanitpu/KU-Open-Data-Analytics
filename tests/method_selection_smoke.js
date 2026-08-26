const assert=require('assert');
const methods=require('../src/method-selection.js');

function field(name,storage,level,unique,{shape='roughly_symmetric',iqr=0,mad=0}={}){
  const f={name,storage_type:storage,measurement_level:level,profile:{unique}};
  if(storage==='numeric'){
    f.distribution={shape};
    f.outliers={method_iqr:{pct:iqr},method_mad:{pct:mad}};
  }else f.frequency={top:[],redacted:false};
  return f;
}
const manifest={fields:[
  field('Income','numeric','Scale',100,{shape:'strong_right_skew',iqr:7}),
  field('Age','numeric','Scale',60),
  field('Spend','numeric','Scale',90),
  field('Segment','text','Nominal',3),
  field('Churn','text','Nominal',2)
]};

let plan={questionType:'predict-outcome',target:'Income',route:'regression',predictors:['Age','Spend','Segment'],methodMode:'recommended',selectedMethods:[]};
let suitable=methods.suitableMethods({plan,manifest});
assert.equal(methods.recommendedMethod(plan,manifest).id,'xgboost-regression');
assert(suitable.some(m=>m.id==='linear-regression'&&m.engine==='browser'));
assert(!suitable.some(m=>m.id==='pearson-correlation'),'Pearson is supporting Explain Drivers, not generic Predict outcome');
assert(methods.effectiveMethodIds(plan,manifest).includes('xgboost-regression'));
const ols=suitable.find(m=>m.id==='linear-regression');
assert(ols.profile_notes.join(' ').includes('reviewing transformations'),'OLS should reflect skew/outlier profile signals');

plan={...plan,questionType:'explain-drivers',methodMode:'custom',selectedMethods:['linear-regression','pearson-correlation','spearman-correlation']};
suitable=methods.suitableMethods({plan,manifest});
for(const id of ['xgboost-regression','linear-regression','pearson-correlation','spearman-correlation'])assert(suitable.some(m=>m.id===id),`missing ${id}`);
assert.deepStrictEqual(methods.effectiveMethodIds(plan,manifest).sort(),['linear-regression','pearson-correlation','spearman-correlation'].sort());

plan={questionType:'predict-outcome',target:'Churn',route:'binary-classification',predictors:['Income','Age'],methodMode:'recommended',selectedMethods:[]};
suitable=methods.suitableMethods({plan,manifest});
assert.deepStrictEqual(suitable.map(m=>m.id),['xgboost-binary']);

plan={questionType:'compare-groups',target:'Income',route:'group-comparison',predictors:['Segment'],methodMode:'custom',selectedMethods:['welch-t-test']};
suitable=methods.suitableMethods({plan,manifest});
for(const id of ['validated-group-comparison','welch-t-test','one-way-anova'])assert(suitable.some(m=>m.id===id),`missing ${id}`);
assert(suitable.find(m=>m.id==='welch-t-test').conditional.includes('exactly 2'));

plan={questionType:'discover-segments',target:null,route:'clustering',predictors:['Income','Age'],methodMode:'recommended',selectedMethods:[]};
assert.deepStrictEqual(methods.suitableMethods({plan,manifest}).map(m=>m.id),['kmeans-clustering']);

plan={questionType:'discover-association-rules',target:null,route:'association',predictors:['Income','Age','Segment'],methodMode:'recommended',selectedMethods:[]};
assert.deepStrictEqual(methods.suitableMethods({plan,manifest}).map(m=>m.id),['mixed-association-screen']);

console.log('[Method Selection smoke completed]');
