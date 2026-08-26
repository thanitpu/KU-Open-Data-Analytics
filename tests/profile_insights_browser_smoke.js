const assert=require('assert');
const {chromium}=require('playwright');

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  await page.goto('http://127.0.0.1:4173/app.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.KUProfileInsights&&window.KUProfileManifest);
  await page.evaluate(()=>{
    document.getElementById('paste').value=[
      'Date,Sales,Income,Segment',
      '2026-01-01,10,20,A',
      '2026-01-02,11,22,A',
      '2026-01-03,12,24,B',
      '2026-01-04,13,26,B',
      '2026-01-05,14,28,A',
      '2026-01-06,15,30,A',
      '2026-01-07,16,32,B',
      '2026-01-08,17,34,A',
      '2026-01-09,18,36,B',
      '2026-01-10,500,1000,A'
    ].join('\n');
    usePaste();
  });
  await page.waitForFunction(()=>!document.querySelector('[data-journey-step="profile"]').disabled);
  await page.click('[data-journey-step="profile"]');
  await page.waitForSelector('.profile-tab[data-profile-tab="distribution"]');
  for(const key of ['distribution','outliers','categorical','relationships','temporal']){
    const node=page.locator(`.profile-tab[data-profile-tab="${key}"]`);
    assert.equal(await node.count(),1,`Missing ${key} tab`);
  }
  await page.click('.profile-tab[data-profile-tab="distribution"]');
  await page.waitForSelector('[data-profile-pane="distribution"].active');
  assert((await page.locator('[data-profile-pane="distribution"]').innerText()).includes('Distribution Shape'));
  assert((await page.locator('[data-profile-pane="distribution"]').innerText()).includes('Sales'));

  await page.click('.profile-tab[data-profile-tab="outliers"]');
  await page.waitForSelector('[data-profile-pane="outliers"].active');
  const outlierText=await page.locator('[data-profile-pane="outliers"]').innerText();
  assert(outlierText.includes('Outlier Detection'));
  assert(outlierText.includes('Income'));

  await page.click('.profile-tab[data-profile-tab="categorical"]');
  await page.waitForSelector('[data-profile-pane="categorical"].active');
  const catText=await page.locator('[data-profile-pane="categorical"]').innerText();
  assert(catText.includes('Categorical Variables Analysis'));
  assert(catText.includes('Segment'));

  await page.click('.profile-tab[data-profile-tab="temporal"]');
  await page.waitForSelector('[data-profile-pane="temporal"].active');
  const temporalText=await page.locator('[data-profile-pane="temporal"]').innerText();
  assert(temporalText.includes('Temporal / Time-Series Patterns'));
  assert(temporalText.toLowerCase().includes('daily'));

  const manifestState=await page.evaluate(()=>({
    rows:window.KUProfileInsights.getManifest()?.dataset_profile?.rows,
    raw:window.KUProfileInsights.getManifest()?.privacy?.row_level_values_included,
    temporal:window.KUProfileInsights.getManifest()?.dataset_profile?.temporal_fields
  }));
  assert.equal(manifestState.rows,10);
  assert.equal(manifestState.raw,false);
  assert.equal(manifestState.temporal,1);
  await browser.close();
  console.log('[Profile Insights browser smoke completed]');
})().catch(err=>{console.error(err);process.exit(1)});
