const assert=require('assert');
const {chromium}=require('playwright');

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:1000}});
  let requestPayload=null;
  await page.route('**/recommend/feature-engineering',async route=>{
    requestPayload=route.request().postDataJSON();
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
      schema_version:'1.0',recommender_version:'rule_based_v1',domain_hints:['customer_analytics'],warnings:[],
      recommendations:[{
        id:'fe_001',source_fields:['Birth_Year'],output_field:'Age',operation:'reference_year_minus',parameters:{reference_year:2026},
        reason:'Birth_Year appears to represent year of birth; age is more directly interpretable for this analysis.',
        basis:['field_semantics','domain_knowledge','analysis_objective'],confidence:.96,category:'feature_engineering',execution:'browser',requires_user_review:true
      }]
    })});
  });
  await page.goto('http://127.0.0.1:4173/app.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.KUFeatureEngineeringReview&&window.KUProfileManifest&&window.KUAppState);
  await page.evaluate(()=>{
    document.getElementById('paste').value=[
      'Birth_Year,Income,MntWines,MntMeatProducts,Response',
      '1980,40000,100,120,No','1980,40000,120,130,No','1982,45000,140,150,No','1982,45000,160,170,Yes',
      '1985,50000,180,190,No','1985,50000,200,210,Yes','1988,55000,220,230,No','1988,55000,240,250,Yes',
      '1990,60000,260,270,No','1990,60000,280,290,Yes','1992,65000,300,310,No','1992,65000,320,330,Yes'
    ].join('\n');
    usePaste();
  });
  await page.waitForFunction(()=>!document.querySelector('[data-journey-step="analyze"]').disabled);
  await page.click('[data-journey-step="analyze"]');
  await page.click('[data-question-type="predict-outcome"]');
  await page.selectOption('#analysisTarget','Response');
  await page.waitForFunction(()=>document.querySelector('#kuMethodChoice')?.innerText.includes('XGBoost Binary Classification'));
  await page.click('#continuePrepare');
  await page.waitForFunction(()=>window.KUAppState.getState().currentStep==='prepare');
  await page.waitForFunction(()=>document.querySelector('#feRecommendationReview')?.innerText.includes('Age'));

  assert(requestPayload,'FE recommendation request should be sent');
  assert.equal(requestPayload.generated_by,'browser');
  assert.equal(requestPayload.privacy.row_level_values_included,false);
  assert(!Object.prototype.hasOwnProperty.call(requestPayload,'data'),'raw dataset rows must not be attached');
  assert.equal(requestPayload.analysis_intent.question_type,'predict-outcome');
  assert.equal(requestPayload.analysis_intent.target,'Response');
  const birth=requestPayload.fields.find(f=>f.name==='Birth_Year');
  const target=requestPayload.fields.find(f=>f.name==='Response');
  assert(birth&&birth.distribution,'numeric field distribution must be sent');
  assert(target&&target.frequency,'categorical field frequency summary must be sent');
  assert.equal(birth.selected_for_analysis,true);
  assert.equal(target.analysis_role,'target');

  let text=await page.locator('#feRecommendationReview').innerText();
  assert(text.includes('Review suggested derived features'));
  assert(text.includes('Profile-only request'));
  assert(text.includes('customer analytics'));
  assert.equal(await page.locator('#continueSetup').isDisabled(),true,'Preparation approval waits for FE review');
  await page.click('[data-fe-confirm]');
  await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.preparation.featureEngineering?.reviewed===true);
  assert.equal(await page.locator('#continueSetup').isDisabled(),false,'Confirmed FE choices allow preparation approval');
  const state=await page.evaluate(()=>window.KUAppState.getState().analysisPlan.preparation.featureEngineering);
  assert.deepStrictEqual(state.selectedIds,['fe_001']);
  assert.equal(state.recommenderVersion,'rule_based_v1');

  await page.click('[data-fe-edit]');
  await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.preparation.featureEngineering?.reviewed===false);
  assert.equal(await page.locator('#continueSetup').isDisabled(),true,'Editing FE choices re-opens the review gate');

  await browser.close();
  console.log('[Feature Engineering review browser smoke completed]');
})().catch(err=>{console.error(err);process.exit(1)});
