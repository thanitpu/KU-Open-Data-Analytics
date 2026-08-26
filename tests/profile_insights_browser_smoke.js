const assert=require('assert');
const {chromium}=require('playwright');

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  await page.goto('http://127.0.0.1:4173/app.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.KUProfileInsights&&window.KUProfileManifest);

  // Existing small-dataset coverage.
  await page.evaluate(()=>{
    document.getElementById('paste').value=[
      'Date,Sales,Income,Segment',
      '2026-01-01,10,20,A','2026-01-02,11,22,A','2026-01-03,12,24,B','2026-01-04,13,26,B','2026-01-05,14,28,A',
      '2026-01-06,15,30,A','2026-01-07,16,32,B','2026-01-08,17,34,A','2026-01-09,18,36,B','2026-01-10,500,1000,A'
    ].join('\n');
    usePaste();
  });
  await page.waitForFunction(()=>!document.querySelector('[data-journey-step="profile"]').disabled);
  await page.click('[data-journey-step="profile"]');
  await page.waitForSelector('.profile-tab[data-profile-tab="distribution"]');
  for(const key of ['distribution','outliers','categorical','relationships','temporal'])assert.equal(await page.locator(`.profile-tab[data-profile-tab="${key}"]`).count(),1,`Missing ${key} tab`);
  await page.click('.profile-tab[data-profile-tab="distribution"]');
  await page.waitForSelector('[data-profile-pane="distribution"].active');
  assert((await page.locator('[data-profile-pane="distribution"]').innerText()).includes('Distribution Shape'));
  await page.click('.profile-tab[data-profile-tab="outliers"]');
  assert((await page.locator('[data-profile-pane="outliers"]').innerText()).includes('Outlier Detection'));
  await page.click('.profile-tab[data-profile-tab="categorical"]');
  assert((await page.locator('[data-profile-pane="categorical"]').innerText()).includes('Categorical Variables Analysis'));

  // Real browser large-dataset path: 120,001 rows triggers the 100k profile sample.
  await page.evaluate(()=>{
    const n=120001;
    headers=['Quantity','UnitPrice','Country','CustomerID'];
    data=Array.from({length:n},(_,i)=>({Quantity:String((i%20)+1),UnitPrice:String((i%1000)/10),Country:['UK','France','Germany','Spain'][i%4],CustomerID:`C${i%5000}`}));
    types={Quantity:'numeric',UnitPrice:'numeric',Country:'text',CustomerID:'text'};
    meta={Quantity:{label:'',storage:'numeric',level:'Scale'},UnitPrice:{label:'',storage:'numeric',level:'Scale'},Country:{label:'',storage:'text',level:'Nominal'},CustomerID:{label:'',storage:'text',level:'Nominal'}};
    window.KUProfileManifest.clearCache?.();
    document.getElementById('status').textContent=`${n} rows × 4 variables loaded`;
    window.KUProfileInsights.render();
    window.KULargeDatasetProfile?.render();
  });
  await page.waitForSelector('#largeProfileMode');
  assert((await page.locator('#largeProfileMode').innerText()).includes('100,000'));

  const expectedTop=await page.locator('#variablesView .step-kicker').boundingBox().then(b=>Math.round(b.y));
  for(const key of ['distribution','outliers','categorical']){
    await page.click(`.profile-tab[data-profile-tab="${key}"]`);
    await page.waitForSelector(`[data-profile-pane="${key}"].active`);
    const text=await page.locator(`[data-profile-pane="${key}"]`).innerText();
    assert(text.trim().length>20,`${key} pane should not be blank for a large dataset`);
    const top=await page.locator('#variablesView .step-kicker').boundingBox().then(b=>Math.round(b.y));
    assert(Math.abs(top-expectedTop)<=2,`${key} changed STEP 2 header position: ${top} vs ${expectedTop}`);
  }
  assert((await page.locator('[data-profile-pane="distribution"]').innerText()).includes('Distribution Shape'));
  assert((await page.locator('[data-profile-pane="outliers"]').innerText()).includes('Outlier Detection'));
  assert((await page.locator('[data-profile-pane="categorical"]').innerText()).includes('Categorical Variables Analysis'));
  const manifest=await page.evaluate(()=>window.KUProfileInsights.getManifest());
  assert.equal(manifest.dataset_profile.rows,120001);
  assert.equal(manifest.profile_provenance.mode,'sampled');
  assert.equal(manifest.profile_provenance.profile_rows,100000);

  await browser.close();
  console.log('[Profile Insights browser smoke completed]');
})().catch(err=>{console.error(err);process.exit(1)});
