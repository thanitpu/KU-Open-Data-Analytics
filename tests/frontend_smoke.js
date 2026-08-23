const assert=require('assert');
const fs=require('fs');
const path=require('path');
const root=path.resolve(__dirname,'..');
const rel=require(path.join(root,'src/relationship-stats.js'));
function near(actual,expected,eps=1e-9){assert.ok(Math.abs(actual-expected)<=eps,`${actual} != ${expected}`)}
near(rel.pearson([1,2,3],[2,4,6]),1);
near(rel.correlation([1,2,3],[10,30,20],'spearman'),0.5);
const cv=rel.chiSquareCramersV([['A','X'],['A','X'],['B','Y'],['B','Y']]);near(cv.cramersV,1);assert.strictEqual(cv.df,1);
const eta=rel.etaSquaredByGroup([1,1,3,3],['A','A','B','B']);near(eta.etaSquared,1);assert.strictEqual(eta.groups.length,2);
require(path.join(root,'src/state.js'));
const s=globalThis.KUAppState;
s.setDataset({loaded:true,rowCount:4,columnCount:3,fields:[{name:'x'},{name:'y'},{name:'target'}]});
assert.strictEqual(s.canEnterStep('analyze'),true,'Analyze should unlock after dataset load');
assert.strictEqual(s.canEnterStep('prepare'),false,'Prepare must remain locked without a derived Analysis Plan route');
s.updateAnalysisPlan({questionType:'Predict an outcome',target:'target',analyticalFamily:'Binary Classification'});
assert.strictEqual(s.canEnterStep('prepare'),false,'Question and target alone must not bypass route derivation');
s.updateAnalysisPlan({route:'binary-classification'});
assert.strictEqual(s.canEnterStep('prepare'),true,'Prepare should unlock after the route is derived');
s.setResultPayload({ok:true});
s.setPredictors(['x']);assert.strictEqual(s.getState().result.validated,true,'predictor-only change must preserve result');
s.updateAnalysisPlan({target:'y'});assert.strictEqual(s.getState().result.validated,false,'target change must reset result');
s.setResultPayload({ok:true});s.updateAnalysisPlan({questionType:'Compare groups'});assert.strictEqual(s.getState().result.validated,false,'question type change must reset result');

// Measurement/storage metadata changes preserve the previous result for comparison,
// but invalidate preparation/setup even when the analytical route itself is unchanged.
s.resetAnalysis();
s.setDataset({loaded:true,revision:10,rowCount:4,columnCount:3,fields:[{name:'x',storage:'numeric',level:'Scale'},{name:'y',storage:'numeric',level:'Scale'},{name:'target',storage:'text',level:'Ordinal'}]});
s.updateAnalysisPlan({questionType:'predict-outcome',target:'target',predictors:['x'],predictorMode:'all-suitable',analyticalFamily:'Regression',route:'regression'});
s.setPreparation({status:'approved',approved:true});
s.setSetup({confirmed:true});
s.setResultPayload({ok:true});
let metaState=s.getState();
assert.strictEqual(metaState.result.planSnapshot.datasetRevision,10);
assert.deepStrictEqual(metaState.result.planSnapshot.fieldMetadata,[{name:'x',storage:'numeric',level:'Scale'},{name:'target',storage:'text',level:'Ordinal'}]);
s.setDataset({loaded:true,revision:10,rowCount:4,columnCount:3,fields:[{name:'x',storage:'numeric',level:'Scale'},{name:'y',storage:'numeric',level:'Scale'},{name:'target',storage:'text',level:'Scale'}]});
metaState=s.getState();
assert.strictEqual(metaState.result.validated,true,'metadata-only edits must preserve the previous result for comparison');
assert.strictEqual(metaState.analysisPlan.preparation.approved,false,'metadata-only edits must invalidate preparation approval');
assert.strictEqual(Boolean(metaState.analysisPlan.setup.confirmed),false,'metadata-only edits must invalidate setup confirmation');

// A newly loaded dataset must reset analysis even if row count, columns and metadata are identical.
s.setPreparation({status:'approved',approved:true});
s.setResultPayload({ok:true});
s.setDataset({loaded:true,revision:11,rowCount:4,columnCount:3,fields:[{name:'x',storage:'numeric',level:'Scale'},{name:'y',storage:'numeric',level:'Scale'},{name:'target',storage:'text',level:'Scale'}]});
const replaced=s.getState();
assert.strictEqual(replaced.dataset.revision,11);
assert.strictEqual(replaced.result.validated,false,'same-schema dataset replacement must clear the previous result');
assert.strictEqual(replaced.analysisPlan.questionType,null,'same-schema dataset replacement must clear the Analysis Plan');
assert.strictEqual(replaced.currentStep,'start','dataset replacement should return the journey to Start');

const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const appJs=fs.readFileSync(path.join(root,'src/app.js'),'utf8');
const analytics=fs.readFileSync(path.join(root,'src/ai-analytics.js'),'utf8');
const journey=fs.readFileSync(path.join(root,'src/journey.js'),'utf8');
const workflow=fs.readFileSync(path.join(root,'src/workflow-steps.js'),'utf8');
const resultDetails=fs.readFileSync(path.join(root,'src/result-details.js'),'utf8');
for(const id of ['workspaceView','variablesView','profileOverview','profileQuality','relFieldA','relFieldB','relationshipResult','aiAnalyticsView'])assert.ok(html.includes(`id="${id}"`),`missing required UI id ${id}`);
for(const src of ['src/state.js','src/advanced-stats.js','src/ai-analytics.js','src/relationship-stats.js','src/data-profile.js','src/workflow-steps.js','src/result-drivers.js','src/result-details.js','src/accessibility.js','src/journey.js'])assert.ok(html.includes(`src="${src}"`),`missing direct script ${src}`);
assert.ok(html.includes('href="src/workflow-steps.css"'),'workflow CSS should load directly from the app shell');
assert.ok(!html.includes('src/v05.js'),'versioned v05 runtime must not be loaded');
assert.ok(!html.includes('hotfix-v051'),'legacy hotfix must not be loaded from index');
assert.ok(!appJs.includes('hotfix-v051'),'legacy hotfix must not be dynamically loaded from app.js');
assert.ok(!appJs.includes("h.onload=()=>{const i=document.createElement('script');i.src='src/i18n.js'"),'legacy hotfix-gated i18n loader must not return');
assert.ok(analytics.includes("const KU_ANALYTICS_API_BASE=(window.KU_ANALYTICS_API_BASE||'https://ku-open-data-analytics-api.onrender.com')"),'analytics client should define the shared configurable API base');
assert.ok(workflow.includes('`${KU_ANALYTICS_API_BASE}/capabilities`'),'Step 5 capabilities must use the same API base as analysis execution');
assert.ok(!workflow.includes('root.KU_ANALYTICS_API_BASE'),'Step 5 must not assume a top-level const is a window property');
assert.ok(journey.includes('datasetRevision'),'journey should track monotonic dataset revisions');
assert.ok(journey.includes('data!==lastDataReference'),'dataset revision must advance when the loader replaces the data array');
assert.ok(journey.includes("variableTable.addEventListener('change'"),'measurement-level edits should sync metadata directly into application state');
for(const text of ['Automatically handled','Needs review','Approve Preparation →','Run recommended analysis →','Technical Run Specification','Backend API'])assert.ok(workflow.includes(text),`missing accepted workflow text: ${text}`);
assert.ok(!workflow.includes('Continue to Setup →'),'obsolete Step 4 forward CTA must not return');
assert.strictEqual((workflow.match(/<div class=\"cm-head\">Actual \+<\/div>/g)||[]).length,1,'binary confusion matrix must contain one Actual + row');
assert.ok(workflow.includes('Number.isInteger(v)'),'integer evidence metrics should render without forced decimal padding');
assert.ok(resultDetails.includes('fieldMetadata'),'Step 6 details should compare result field metadata for freshness');
assert.ok(resultDetails.includes('Field storage or measurement metadata changed'),'metadata mismatch should have an explicit stale-result disclosure');
for(const f of ['src/advanced-stats.js','src/workflow-steps.js','src/workflow-steps.css','src/result-drivers.js','src/result-details.js','src/accessibility.js'])assert.ok(fs.existsSync(path.join(root,f)),`missing production asset ${f}`);
console.log('FRONTEND_SMOKE_OK');
