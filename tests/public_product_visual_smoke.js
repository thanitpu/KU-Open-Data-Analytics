const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {chromium}=require('playwright');

const baseURL=(process.env.KU_VISUAL_BASE_URL||'http://127.0.0.1:4173').replace(/\/$/,'');
const artifactDir=path.resolve(__dirname,'..','test-artifacts','visual-uat');
fs.mkdirSync(artifactDir,{recursive:true});

async function noHorizontalOverflow(page,label){
  const d=await page.evaluate(()=>({innerWidth,html:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
  assert.ok(d.html<=d.innerWidth+2&&d.body<=d.innerWidth+2,`${label}: horizontal overflow inner=${d.innerWidth}, html=${d.html}, body=${d.body}`);
}
async function runViewport(browser,viewport){
  const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height}});
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',err=>errors.push(`pageerror: ${err.message}`));
  page.on('console',msg=>{if(msg.type()==='error')errors.push(`console: ${msg.text()}`)});
  page.on('response',response=>{if(response.status()>=400&&!response.url().endsWith('/favicon.ico'))errors.push(`http ${response.status()}: ${response.url()}`)});
  await page.route('https://fonts.googleapis.com/**',route=>route.fulfill({status:200,contentType:'text/css',body:''}));
  await page.route('https://fonts.gstatic.com/**',route=>route.fulfill({status:204,body:''}));
  await page.route('https://cdn.jsdelivr.net/**',route=>route.fulfill({status:200,contentType:'application/javascript',body:'window.XLSX=window.XLSX||{};window.jStat=window.jStat||{};'}));

  await page.goto(`${baseURL}/index.html`,{waitUntil:'domcontentloaded'});
  await page.waitForSelector('#siteHeader');
  assert.ok(await page.locator('#hero').isVisible(),`${viewport.name}: Public hero should be visible`);
  assert.strictEqual(await page.locator('#workspaceView').count(),0,`${viewport.name}: Product shell must not leak into Landing`);
  const cta=page.locator('.hero-cta a.btn[href="app.html"]');
  assert.strictEqual(await cta.count(),1,`${viewport.name}: Hero must expose one primary Start analyzing CTA`);
  assert.ok(await cta.isVisible(),`${viewport.name}: Hero Start analyzing CTA should remain visible`);
  await noHorizontalOverflow(page,`${viewport.name}/landing`);
  await page.screenshot({path:path.join(artifactDir,`${viewport.name}-landing.png`),fullPage:true});

  await Promise.all([
    page.waitForURL(url=>url.pathname.endsWith('/app.html')),
    cta.click()
  ]);
  await page.waitForSelector('#workspaceView');
  assert.ok(await page.locator('#workspaceView').isVisible(),`${viewport.name}: Product workspace should open from Landing CTA`);
  assert.strictEqual(await page.locator('#siteHeader').count(),0,`${viewport.name}: Landing header must not leak into Product`);
  await noHorizontalOverflow(page,`${viewport.name}/app-entry`);
  assert.deepStrictEqual(errors,[],`${viewport.name}: browser errors detected:\n${errors.join('\n')}`);
  await context.close();
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    for(const viewport of [
      {name:'desktop-1440',width:1440,height:900},
      {name:'tablet-900',width:900,height:1000},
      {name:'mobile-390',width:390,height:844}
    ]) await runViewport(browser,viewport);
    console.log('PUBLIC_PRODUCT_VISUAL_SMOKE_OK (index.html → app.html)');
  }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exit(1)});
