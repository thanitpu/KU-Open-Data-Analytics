const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]+src="https:[^"]+"[^>]*><\/script>/g,'').replace(/<script src="src\/[^"]+"><\/script>/g,'');
const dom=new JSDOM(html,{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;
w.alert=msg=>{throw new Error(`Unexpected alert: ${msg}`)};
w.HTMLCanvasElement.prototype.getContext=function(){return new Proxy({},{get:(t,p)=>p==='measureText'?(()=>({width:10})):(p==='canvas'?this:(()=>{})),set:(t,p,v)=>true})};
const scripts=['src/state.js','src/app.js','src/analysis.js','src/v05.js','src/ai-analytics.js','src/relationship-stats.js','src/data-profile.js','src/journey.js'];
w.eval(scripts.map(f=>fs.readFileSync(path.join(root,f),'utf8')).join('\n;\n'));
w.document.dispatchEvent(new w.Event('DOMContentLoaded',{bubbles:true}));
const tick=()=>new Promise(r=>w.setTimeout(r,0));
(async()=>{
  w.demo();await tick();
  assert.strictEqual(w.document.getElementById('rows').textContent,'9');
  assert.ok(w.document.getElementById('startDatasetBand').classList.contains('show'),'loaded dataset band should show');
  const profileButton=w.document.querySelector('[data-journey-step="profile"]');
  assert.strictEqual(profileButton.disabled,false,'Data Profile should unlock after dataset load');
  w.goToJourneyStep('profile');await tick();
  assert.ok(!w.document.getElementById('variablesView').classList.contains('hidden'),'Step 2 should render');
  assert.strictEqual(w.document.getElementById('profileRows').textContent,'9');
  assert.ok(w.document.getElementById('profileOverview').textContent.includes('Field structure'));
  w.setProfileTab('quality');
  assert.ok(w.document.querySelector('[data-profile-pane="quality"]').classList.contains('active'));
  assert.ok(w.document.getElementById('profileQuality').textContent.includes('Cell completeness'));
  w.setProfileTab('relationships');
  const a=w.document.getElementById('relFieldA'),b=w.document.getElementById('relFieldB');
  a.value='Score';b.value='Age';w.updateProfileRelationshipMethod();w.runProfileRelationship();
  assert.ok(w.document.getElementById('relationshipResult').textContent.includes('Pearson r'),'Scale↔Scale should route to correlation');
  a.value='Group';b.value='Score';w.updateProfileRelationshipMethod();w.runProfileRelationship();
  assert.ok(w.document.getElementById('relationshipResult').textContent.includes('eta squared'),'Scale↔categorical should route to eta squared');
  a.value='Group';b.value='Satisfaction';w.updateProfileRelationshipMethod();w.runProfileRelationship();
  assert.ok(w.document.getElementById('relationshipResult').textContent.includes('Cramér'),'categorical↔categorical should route to Cramér’s V');

  // Step 3: question first, target second, family derived automatically.
  w.goToJourneyStep('analyze');await tick();
  assert.ok(!w.document.getElementById('aiAnalyticsView').classList.contains('hidden'),'Step 3 should render');
  assert.ok(w.document.getElementById('aiAnalyticsView').textContent.includes('What do you want to learn?'));
  w.document.querySelector('[data-question-type="predict-outcome"]').click();
  let target=w.document.getElementById('analysisTarget');target.value='Satisfaction';target.dispatchEvent(new w.Event('change',{bubbles:true}));
  let state=w.KUAppState.getState();
  assert.strictEqual(state.analysisPlan.questionType,'predict-outcome');
  assert.strictEqual(state.analysisPlan.target,'Satisfaction');
  assert.strictEqual(state.analysisPlan.analyticalFamily,'Multiclass Classification');
  assert.strictEqual(state.analysisPlan.route,'multiclass-classification');
  assert.ok(state.analysisPlan.predictors.includes('Score')&&state.analysisPlan.predictors.includes('Age'),'all suitable fields should be selected');
  assert.ok(w.document.getElementById('aiAnalyticsView').textContent.includes('Validated FastAPI route'));

  // Predictor changes preserve the last validated result, per product rule.
  w.KUAppState.setResultPayload({result:{status:'COMPLETE'}});
  let custom=w.document.querySelector('input[name="predictorMode"][value="custom"]');custom.checked=true;custom.dispatchEvent(new w.Event('change',{bubbles:true}));
  let predictor=w.document.querySelector('[data-predictor="Age"]');predictor.checked=false;predictor.dispatchEvent(new w.Event('change',{bubbles:true}));
  state=w.KUAppState.getState();
  assert.strictEqual(state.analysisPlan.predictorMode,'custom');
  assert.strictEqual(state.result.validated,true,'predictor edit must preserve validated result');
  assert.strictEqual(state.analysisPlan.preparation.approved,false,'predictor edit must invalidate downstream preparation approval');

  // Target changes invalidate the result and re-derive the family.
  target=w.document.getElementById('analysisTarget');target.value='Score';target.dispatchEvent(new w.Event('change',{bubbles:true}));
  state=w.KUAppState.getState();
  assert.strictEqual(state.analysisPlan.analyticalFamily,'Regression');
  assert.strictEqual(state.result.validated,false,'target change must reset result');

  // Target-free discovery route.
  w.document.querySelector('[data-question-type="discover-segments"]').click();
  state=w.KUAppState.getState();
  assert.strictEqual(state.analysisPlan.target,null);
  assert.strictEqual(state.analysisPlan.analyticalFamily,'Clustering / Segmentation');
  assert.deepStrictEqual([...state.analysisPlan.predictors].sort(),['Age','Score'].sort(),'segmentation defaults to numeric Scale fields');

  // Compare groups uses the existing statistical module rather than a fake FastAPI route.
  w.document.querySelector('[data-question-type="compare-groups"]').click();
  target=w.document.getElementById('analysisTarget');target.value='Score';target.dispatchEvent(new w.Event('change',{bubbles:true}));
  state=w.KUAppState.getState();
  assert.strictEqual(state.analysisPlan.route,'group-comparison');
  assert.ok(w.document.getElementById('aiAnalyticsView').textContent.includes('Existing statistical module'));
  assert.ok(state.analysisPlan.predictors.includes('Group'),'categorical grouping field should be suitable');

  // Working batch boundary: Continue reaches a truthful Step 4 integration boundary page.
  w.document.getElementById('continuePrepare').click();await tick();
  assert.ok(!w.document.getElementById('journeyPendingView').classList.contains('hidden'),'Prepare boundary should be navigable');
  assert.ok(w.document.getElementById('journeyPendingView').textContent.includes('Analysis Plan saved'));
  w.goToJourneyStep('analyze');await tick();
  state=w.KUAppState.getState();assert.strictEqual(state.analysisPlan.target,'Score','Analysis Plan should restore after navigation');

  w.goToJourneyStep('start');w.clearAll();await tick();
  assert.ok(!w.document.getElementById('startDatasetBand').classList.contains('show'),'dataset band should hide after clear');
  assert.strictEqual(w.KUAppState.getState().analysisPlan.questionType,null,'clearing/replacing dataset should clear stale Analysis Plan');
  console.log('FRONTEND_DOM_SMOKE_OK');
})().catch(err=>{console.error(err);process.exit(1)});
