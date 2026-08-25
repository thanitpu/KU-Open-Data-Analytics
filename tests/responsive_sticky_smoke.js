const assert=require('assert');
const {chromium}=require('playwright');
const baseURL=(process.env.KU_VISUAL_BASE_URL||'http://127.0.0.1:4173').replace(/\/$/,'');
const appURL=`${baseURL}/${process.env.KU_APP_ENTRY||'app.html'}`;
async function runViewport(browser,{name,width,height}){
  const context=await browser.newContext({viewport:{width,height}});const page=await context.newPage();
  await page.route('**/favicon.ico',r=>r.fulfill({status:204,body:''}));
  await page.route('https://cdn.jsdelivr.net/**',r=>r.fulfill({status:200,contentType:'application/javascript',body:'window.XLSX=window.XLSX||{};window.jStat=window.jStat||{};'}));
  await page.goto(appURL,{waitUntil:'domcontentloaded'});await page.waitForSelector('#workspaceView');
  await page.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--ku-product-header-height').trim()!=='');
  const initial=await page.evaluate(()=>{const h=document.querySelector('header'),a=document.querySelector('aside'),m=document.querySelector('main'),actions=document.querySelector('header .actions'),hr=h.getBoundingClientRect(),ar=a.getBoundingClientRect(),mr=m.getBoundingClientRect(),xr=actions.getBoundingClientRect();return{headerPos:getComputedStyle(h).position,asidePos:getComputedStyle(a).position,asideTop:parseFloat(getComputedStyle(a).top),headerHeight:hr.height,headerBottom:hr.bottom,asideRectTop:ar.top,asideBottom:ar.bottom,mainTop:mr.top,actionsBottom:xr.bottom,htmlWidth:document.documentElement.scrollWidth,innerWidth:innerWidth}});
  assert.strictEqual(initial.headerPos,'sticky',`${name}: header must be sticky`);assert.strictEqual(initial.asidePos,'sticky',`${name}: workflow must be sticky`);
  assert.ok(Math.abs(initial.asideTop-initial.headerHeight)<=2,`${name}: workflow sticky top must track actual header height`);
  assert.ok(initial.actionsBottom<=initial.headerBottom+2,`${name}: header actions must stay inside header instead of floating over main`);
  assert.ok(initial.mainTop>=initial.asideBottom-2,`${name}: main content must start below workflow in normal flow`);
  assert.ok(initial.htmlWidth<=initial.innerWidth+2,`${name}: page must not overflow horizontally`);
  await page.evaluate(()=>window.scrollTo(0,Math.min(500,document.documentElement.scrollHeight-innerHeight)));await page.waitForTimeout(100);
  const sticky=await page.evaluate(()=>{const h=document.querySelector('header').getBoundingClientRect(),a=document.querySelector('aside').getBoundingClientRect();return{headerTop:h.top,headerBottom:h.bottom,asideTop:a.top}});
  assert.ok(Math.abs(sticky.headerTop)<=2,`${name}: header should remain pinned at viewport top`);
  assert.ok(Math.abs(sticky.asideTop-sticky.headerBottom)<=2,`${name}: workflow should remain pinned immediately below header`);
  await context.close();
}
(async()=>{const browser=await chromium.launch({headless:true});try{for(const vp of[{name:'tablet-900',width:900,height:1000},{name:'mobile-390',width:390,height:844}])await runViewport(browser,vp);console.log('RESPONSIVE_STICKY_SMOKE_OK (header + workflow stack)')}finally{await browser.close()}})().catch(err=>{console.error(err);process.exit(1)});
