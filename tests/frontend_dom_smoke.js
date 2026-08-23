const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]+src="https:[^"]+"[^>]*><\/script>/g,'').replace(/<script src="src\/[^"]+"><\/script>/g,'');
const dom=new JSDOM(html,{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;
w.alert=msg=>{throw new Error(`Unexpected alert: ${msg}`)};
w.HTMLCanvasElement.prototype.getContext=function(){return new Proxy({},{get:(t,p)=>p==='measureText'?(()=>({width:10})):(p==='canvas'?this:(()=>{})),set:()=>true})};
const capabilities={service:{mode:'fast'},routes:{'group-comparison':{intent:'Compare Groups',policy:{two_groups:'Welch t-test',three_or_more_groups:'One-way ANOVA'},preparation:{missing:'complete-case'},validation:'Inferential group comparison',metrics:['p_value','hedges_g']},regression:{intent:'Regression',policy:{model:'XGBoost'},preparation:{missing_numeric:'median imputation'},validation:'5-fold KFold',metrics:['mae','rmse','r2']}}};
w.fetch=async(url)=>{
  if(String(url).endsWith('/capabilities'))return{ok:true,status:200,json:async()=>capabilities};
  if(String(url).endsWith('/analyze'))return{ok:true,status:200,json:async()=>({result:{status:'COMPLETE',route:'compare_groups',analysis_type:'multi_group_comparison',target:'Score',method:{test:'One-way ANOVA',grouping_field:'Group'},evidence:{f:12.5,p_value:.002,eta_squared:.72,groups:3,n_total:9},findings:[],warnings:[],readiness:'FAST_EXECUTION_READY'},report:{overview:[{label:'Analysis',value:'multi_group_comparison'}],method:[{label:'Test',value:'One-way ANOVA'}],evidence:[{label:'p value',value:'0.002'}],findings:[]}})};
  throw new Error(`Unexpected fetch ${url}`);
};
const scripts=['src/state.js','src/app.js','src/analysis.js','src/v05.js','src/ai-analytics.js','src/relationship-stats.js','src/data-profile.js','src/workflow-steps.js','src/result-drivers.js','src/accessibility.js','src/journey.js'];
w.eval(scripts.map(f=>fs.readFileSync(path.join(root,f),'utf8')).join('\n;\n'));
w.document.dispatchEvent(new w.Event('DOMContentLoaded',{bubbles:true}));
const tick=()=>new Promise(r=>w.setTimeout(r,0));
(async()=>{
  w.demo();await tick();assert.strictEqual(w.document.getElementById('rows').textContent,'9');

  // Legacy Data Workspace/Variables navigation must synchronize the six-step state.
  w.showView('variables');await tick();assert.strictEqual(w.KUAppState.getState().currentStep,'profile');
  const overviewTab=w.document.querySelector('[data-profile-tab="overview"]');assert.strictEqual(overviewTab.getAttribute('role'),'tab');assert.strictEqual(overviewTab.getAttribute('aria-selected'),'true');
  overviewTab.focus();overviewTab.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));await tick();assert.strictEqual(w.document.querySelector('[data-profile-tab="fields"]').getAttribute('aria-selected'),'true');assert.strictEqual(w.document.querySelector('[data-profile-pane="overview"]').hidden,true);

  w.goToJourneyStep('profile');await tick();assert.strictEqual(w.document.getElementById('profileRows').textContent,'9');
  w.setProfileTab('relationships');let a=w.document.getElementById('relFieldA'),b=w.document.getElementById('relFieldB');a.value='Score';b.value='Age';w.runProfileRelationship();assert.ok(w.document.getElementById('relationshipResult').textContent.includes('Pearson r'));
  w.goToJourneyStep('analyze');await tick();w.showAnalysisView('frequency');assert.ok(w.document.getElementById('aiAnalyticsView').classList.contains('hidden'),'advanced analysis must not overlap Analyze');w.goToJourneyStep('analyze');await tick();
  w.document.querySelector('[data-question-type="predict-outcome"]').click();let target=w.document.getElementById('analysisTarget');target.value='Group';target.dispatchEvent(new w.Event('change',{bubbles:true}));let state=w.KUAppState.getState();assert.strictEqual(state.analysisPlan.route,'multiclass-classification');
  w.document.querySelector('[data-question-type="compare-groups"]').click();target=w.document.getElementById('analysisTarget');target.value='Score';target.dispatchEvent(new w.Event('change',{bubbles:true}));state=w.KUAppState.getState();assert.strictEqual(state.analysisPlan.route,'group-comparison');assert.ok(state.analysisPlan.predictors.includes('Group'));
  w.document.getElementById('continuePrepare').click();await tick();assert.ok(w.document.getElementById('journeyPendingView').textContent.includes('Preparation summary'));
  let group=w.document.getElementById('prepareGroupField');group.value='Group';group.dispatchEvent(new w.Event('change',{bubbles:true}));await tick();assert.strictEqual(w.document.getElementById('continueSetup').disabled,false);w.document.getElementById('continueSetup').click();await tick();await tick();assert.ok(w.document.getElementById('journeyPendingView').textContent.includes('Recommended Setup'));assert.strictEqual(w.document.getElementById('runAnalysisBtn').disabled,false);
  w.document.getElementById('runAnalysisBtn').click();await tick();await tick();assert.ok(w.document.querySelector('.result-answer').textContent.includes('One-way ANOVA'));state=w.KUAppState.getState();assert.strictEqual(state.currentStep,'results');

  // Explain-drivers results surface model-derived importance, not only performance metrics.
  w.goToJourneyStep('analyze');await tick();w.document.querySelector('[data-question-type="explain-drivers"]').click();target=w.document.getElementById('analysisTarget');target.value='Score';target.dispatchEvent(new w.Event('change',{bubbles:true}));
  w.KUAppState.setResultPayload({result:{status:'COMPLETE',route:'regression',analysis_type:'regression',target:'Score',method:{model:'XGBoost'},evidence:{r2:.81,rmse:2.1,mae:1.4},findings:[{relationship:'Age',importance:.42,effect:.42},{relationship:'Group_B',importance:.28,effect:.28},{relationship:'Satisfaction_High',importance:.17,effect:.17}],warnings:['Feature importance is predictive model evidence and does not establish causal drivers.']},report:{overview:[],method:[],evidence:[],findings:[]}});
  w.goToJourneyStep('results');await tick();assert.ok(w.document.querySelector('.result-answer h2').textContent.includes('strongest predictive signals'));assert.ok(w.document.getElementById('predictiveDrivers'));assert.ok(w.document.getElementById('predictiveDrivers').textContent.includes('Age'));assert.strictEqual(w.document.querySelector('.result-stale'),null,'fresh result should not be marked stale');

  // Predictor edits preserve the result but must label it as belonging to an earlier plan.
  w.goToJourneyStep('analyze');await tick();let custom=w.document.querySelector('input[name="predictorMode"][value="custom"]');custom.checked=true;custom.dispatchEvent(new w.Event('change',{bubbles:true}));let age=w.document.querySelector('[data-predictor="Age"]');age.checked=false;age.dispatchEvent(new w.Event('change',{bubbles:true}));state=w.KUAppState.getState();assert.strictEqual(state.result.validated,true,'predictor edit must preserve validated result');w.goToJourneyStep('results');await tick();assert.ok(w.document.querySelector('.result-stale')?.textContent.includes('Previous validated result'),'preserved result must disclose plan mismatch');

  w.goToJourneyStep('start');w.clearAll();await tick();assert.strictEqual(w.KUAppState.getState().analysisPlan.questionType,null);console.log('FRONTEND_DOM_SMOKE_OK');
})().catch(err=>{console.error(err);process.exit(1)});
