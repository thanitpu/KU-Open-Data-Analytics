const assert=require('assert');
const {chromium}=require('playwright');

const base='http://127.0.0.1:4173/app.html';
const api='https://ku-open-data-analytics-api.onrender.com';
const csv=[
  'Age,Spend,Income,Segment',
  '20,10,31000,A','21,13,33400,A','22,18,35900,B','23,22,39100,B',
  '24,28,42100,A','25,35,46800,B','26,39,49700,A','27,47,54800,B','28,56,60300,A'
].join('\n');
const capabilities={service:{version:'0.5.0',mode:'fast',source:'validated_backend'},routes:{regression:{intent:'Regression',policy:{model:'XGBoost'},preparation:{missing_numeric:'median imputation inside CV'},validation:'5-fold shuffled KFold',metrics:['mae','rmse','r2']},'group-comparison':{intent:'Compare Groups',policy:{two_groups:'Welch t-test',three_or_more_groups:'One-way ANOVA'},preparation:{missing:'complete-case'},validation:'group count',metrics:['p_value']}}};
const backendPayload={result:{status:'COMPLETE',route:'regression',analysis_type:'regression',target:'Income',mode:'fast',dataset:{rows:9,columns:4},method:{feature_engineering:'browser_prepared_matrix',model_preprocessing:'CV-safe median imputation + one-hot encoding',model:'XGBoost'},evidence:{mae:1200,rmse:1600,r2:.94,tail_mae:1800,tail_bias:-200},findings:[{relationship:'Spend',effect:.72,importance:.72,interpretation:'Predictive importance'}],warnings:['Feature importance is predictive, not causal.'],preparation:{browser_fe_manifest_received:true,browser_fe_applied:false,derived_fields:[],feature_lineage:[],deterministic_feature_owner:'browser',model_preprocessing_owner:'backend_cv_pipeline',legacy_backend_feature_engineering:false},readiness:'FAST_EXECUTION_READY'},report:{overview:[{label:'Analysis',value:'regression'},{label:'Target',value:'Income'},{label:'Status',value:'COMPLETE'}],method:[{label:'Model',value:'XGBoost'}],evidence:[{label:'R2',value:'0.9400'}],findings:[],warnings:[]}};
const feEmpty={schema_version:'1.0',recommender_version:'rule_based_v1',domain_hints:['general_tabular'],recommendations:[],warnings:[]};

async function boot(browser,{mixed=false}={}){
  const context=await browser.newContext({viewport:{width:1280,height:960}}),page=await context.newPage();
  let analyzeCalls=0,capabilityCalls=0;
  await page.addInitScript(base=>{window.KU_ANALYTICS_API_BASE=base},api);
  await page.route(`${api}/recommend/feature-engineering`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(feEmpty)}));
  await page.route(`${api}/capabilities`,route=>{capabilityCalls++;return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(capabilities)})});
  await page.route(`${api}/analyze`,route=>{analyzeCalls++;return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(backendPayload)})});
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.KUMultiMethod&&window.KUMethodSelection&&window.KUFeatureEngineeringReview&&window.KUAppState);
  await page.evaluate(text=>{document.getElementById('paste').value=text;usePaste()},csv);
  await page.waitForFunction(()=>!document.querySelector('[data-journey-step="analyze"]').disabled);
  await page.click('[data-journey-step="analyze"]');
  await page.click('[data-question-type="explain-drivers"]');
  await page.selectOption('#analysisTarget','Income');
  await page.waitForFunction(()=>document.querySelector('#kuMethodChoice')?.innerText.includes('Linear Regression (OLS)'));
  await page.check('input[name="analysisMethodMode"][value="custom"]');
  await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.methodMode==='custom');
  const ids=mixed?['xgboost-regression','linear-regression','pearson-correlation']:['linear-regression','pearson-correlation','spearman-correlation'];
  for(const id of ids){await page.check(`[data-analysis-method="${id}"]`);await page.waitForFunction(id=>window.KUAppState.getState().analysisPlan.selectedMethods.includes(id),id)}
  await page.click('#continuePrepare');
  await page.waitForFunction(()=>window.KUAppState.getState().currentStep==='prepare');
  await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.preparation.featureEngineering?.reviewed===true);
  await page.waitForFunction(()=>document.getElementById('continueSetup')&&!document.getElementById('continueSetup').disabled);
  await page.click('#continueSetup');
  await page.waitForFunction(()=>window.KUAppState.getState().currentStep==='setup');
  await page.waitForSelector('#runAnalysisBtn:not([disabled])');
  return{context,page,counts:()=>({analyzeCalls,capabilityCalls}),ids};
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    // Local-only: selected methods must never call POST /analyze.
    {
      const {context,page,counts,ids}=await boot(browser,{mixed:false});
      const setup=await page.locator('#multiSetupBody').innerText();
      assert(setup.includes('Local-only execution'));
      assert(setup.includes('3 selected methods'));
      assert.equal(counts().capabilityCalls,0,'local-only Setup must not request backend model capability metadata');
      await page.click('#runAnalysisBtn');
      await page.waitForSelector('.multi-result-list');
      assert.equal(counts().analyzeCalls,0,'local-only selected methods must make zero /analyze calls');
      const state=await page.evaluate(()=>window.KUAppState.getState());
      assert.equal(state.result.source,'multi-method');
      assert.equal(state.result.payload.methods.length,3);
      assert.deepStrictEqual(state.result.payload.execution.requested_method_ids.sort(),ids.sort());
      assert(state.result.payload.methods.every(m=>m.engine==='browser'));
      assert.equal(state.result.payload.execution.backend_analysis_calls,0);
      assert(!JSON.stringify(state.result.payload).includes('A,20,10'),'combined result must not embed raw input rows');
      const resultText=await page.locator('#journeyPendingView').innerText();
      assert(resultText.includes('Linear Regression (OLS)'));
      assert(resultText.includes('Pearson Correlation'));
      assert(resultText.includes('Spearman Correlation'));

      // Predictor change preserves old payload but must mark it stale.
      await page.evaluate(()=>window.KUAppState.updateAnalysisPlan({predictorMode:'custom',predictors:['Age']}));
      await page.evaluate(()=>window.goToJourneyStep('results'));
      await page.waitForSelector('.result-stale');
      assert((await page.locator('.result-stale').innerText()).includes('Previous result'));
      await context.close();
    }

    // Mixed local + backend: all local methods run, but the backend is called exactly once.
    {
      const {context,page,counts}=await boot(browser,{mixed:true});
      const setup=await page.locator('#multiSetupBody').innerText();
      assert(setup.includes('2 local · 1 KU Validated Engine'));
      assert.equal(counts().capabilityCalls,1,'mixed Setup should load backend capability metadata once');
      await page.click('#runAnalysisBtn');
      await page.waitForSelector('.multi-result-list');
      assert.equal(counts().analyzeCalls,1,'mixed execution must make exactly one /analyze call');
      const payload=await page.evaluate(()=>window.KUAppState.getState().result.payload);
      assert.equal(payload.methods.length,3);
      assert.equal(payload.execution.backend_analysis_calls,1);
      assert.equal(payload.primary_method_id,'xgboost-regression');
      assert.equal(payload.result.method.model,'XGBoost','top-level compatibility result should remain the primary backend result');
      assert(payload.methods.some(m=>m.id==='linear-regression'&&m.engine==='browser'&&m.status==='COMPLETE'));
      assert(payload.methods.some(m=>m.id==='pearson-correlation'&&m.engine==='browser'&&m.status==='COMPLETE'));
      assert(payload.methods.some(m=>m.id==='xgboost-regression'&&m.engine==='backend'&&m.status==='COMPLETE'));
      const resultText=await page.locator('#journeyPendingView').innerText();
      assert(resultText.includes('3 selected methods completed'));
      assert(resultText.includes('XGBoost Regression'));
      assert(resultText.includes('Linear Regression (OLS)'));
      await context.close();
    }

    // Method-specific preparation gate: Welch cannot silently run on 3 groups.
    {
      const context=await browser.newContext({viewport:{width:1100,height:900}}),page=await context.newPage();
      await page.addInitScript(base=>{window.KU_ANALYTICS_API_BASE=base},api);
      await page.route(`${api}/recommend/feature-engineering`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(feEmpty)}));
      await page.goto(base,{waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>window.KUMultiMethod&&window.KUMethodSelection&&window.KUFeatureEngineeringReview);
      const groupCsv=['Group,Score','A,10','A,11','A,12','B,20','B,21','B,22','C,30','C,31','C,32'].join('\n');
      await page.evaluate(text=>{document.getElementById('paste').value=text;usePaste()},groupCsv);
      await page.click('[data-journey-step="analyze"]');
      await page.click('[data-question-type="compare-groups"]');
      await page.selectOption('#analysisTarget','Score');
      await page.check('input[name="analysisMethodMode"][value="custom"]');
      await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.methodMode==='custom');
      await page.check('[data-analysis-method="welch-t-test"]');
      await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.selectedMethods.includes('welch-t-test'));
      await page.click('#continuePrepare');
      await page.waitForFunction(()=>window.KUAppState.getState().currentStep==='prepare');
      await page.waitForSelector('#prepareGroupField');
      await page.selectOption('#prepareGroupField','Group');
      await page.waitForSelector('#methodPrepBlockers');
      assert((await page.locator('#methodPrepBlockers').innerText()).includes('exactly 2 complete groups'));
      assert.equal(await page.locator('#continueSetup').isDisabled(),true);
      await context.close();
    }

    console.log('[Multi-method browser integration smoke completed]');
  }finally{await browser.close()}
})().catch(err=>{console.error(err);process.exit(1)});
