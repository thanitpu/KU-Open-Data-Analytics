const assert=require('assert');
const {chromium}=require('playwright');

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  await page.goto('http://127.0.0.1:4173/app.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.KUMethodSelection&&window.KUProfileManifest&&window.KUAppState);
  await page.evaluate(()=>{
    document.getElementById('paste').value=[
      'Age,Spend,Income,Segment,Churn',
      '20,10,30,A,No','21,12,32,A,No','22,14,35,B,No','23,18,39,B,Yes','24,20,42,A,No',
      '25,24,47,B,Yes','26,30,52,A,No','27,36,58,B,Yes','28,44,67,A,No','29,70,140,B,Yes'
    ].join('\n');
    usePaste();
  });
  await page.waitForFunction(()=>!document.querySelector('[data-journey-step="analyze"]').disabled);
  await page.click('[data-journey-step="analyze"]');
  await page.click('[data-question-type="predict-outcome"]');
  await page.selectOption('#analysisTarget','Income');
  await page.waitForSelector('#kuMethodChoice');
  let text=await page.locator('#kuMethodChoice').innerText();
  assert(text.includes('Recommended method'));
  assert(text.includes('XGBoost Regression'));
  assert(text.includes('Linear Regression (OLS)'));
  assert(text.includes('Local · Browser'));
  assert(text.includes('KU Validated Engine'));

  await page.check('input[name="analysisMethodMode"][value="custom"]');
  await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.methodMode==='custom');
  assert.equal(await page.locator('#continuePrepare').isDisabled(),true,'custom mode with no methods should block Continue');
  await page.check('[data-analysis-method="linear-regression"]');
  await page.waitForFunction(()=>window.KUAppState.getState().analysisPlan.selectedMethods.includes('linear-regression'));
  const state=await page.evaluate(()=>window.KUAppState.getState().analysisPlan);
  assert.equal(state.methodMode,'custom');
  assert.deepStrictEqual(state.selectedMethods,['linear-regression']);
  assert.equal(await page.locator('#continuePrepare').isDisabled(),false,'selected custom method should allow Continue when plan is otherwise ready');

  await page.click('[data-question-type="explain-drivers"]');
  await page.selectOption('#analysisTarget','Income');
  await page.waitForSelector('#kuMethodChoice');
  text=await page.locator('#kuMethodChoice').innerText();
  assert(text.includes('Pearson Correlation'));
  assert(text.includes('Spearman Correlation'));
  const resetState=await page.evaluate(()=>window.KUAppState.getState().analysisPlan);
  assert.equal(resetState.methodMode,'recommended','question change should reset method mode');
  assert.deepStrictEqual(resetState.selectedMethods,[],'question change should clear custom methods');

  await browser.close();
  console.log('[Method Selection browser smoke completed]');
})().catch(err=>{console.error(err);process.exit(1)});
