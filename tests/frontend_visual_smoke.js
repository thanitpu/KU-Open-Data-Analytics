const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {chromium}=require('playwright');

const baseURL=(process.env.KU_VISUAL_BASE_URL||'http://127.0.0.1:4173').replace(/\/$/,'');
const appEntry=process.env.KU_APP_ENTRY||'app.html';
const appURL=`${baseURL}/${appEntry}`;
const analyticsBase='https://ku-open-data-analytics-api.onrender.com';
const artifactDir=path.resolve(__dirname,'..','test-artifacts','visual-uat');
fs.mkdirSync(artifactDir,{recursive:true});

const capabilities={
  service:{version:'0.4.0',mode:'fast',source:'validated_backend'},
  routes:{
    'group-comparison':{
      intent:'Compare Groups',target_required:true,options_required:['group'],
      policy:{two_groups:'Welch t-test',three_or_more_groups:'One-way ANOVA'},
      preparation:{target:'numeric coercion',missing:'complete-case outcome/group observations'},
      validation:'Inferential group comparison selected by observed group count',
      metrics:['p_value','mean_difference','hedges_g','eta_squared']
    }
  }
};
const feRecommendationPayload={
  schema_version:'1.0',
  recommender_version:'rule_based_v1',
  domain_hints:['general_tabular'],
  recommendations:[],
  warnings:[]
};
const analysisPayload={
  result:{
    status:'COMPLETE',route:'compare_groups',analysis_type:'multi_group_comparison',target:'Score',mode:'fast',
    method:{test:'One-way ANOVA',grouping_field:'Group'},
    evidence:{f:12.5,p_value:.002,eta_squared:.72,groups:3,n_total:9},
    findings:[],
    group_summaries:[
      {group:'A',n:3,mean:71,sd:2},
      {group:'B',n:3,mean:83,sd:2.5},
      {group:'C',n:3,mean:92,sd:1.5}
    ],
    warnings:[],readiness:'FAST_EXECUTION_READY'
  },
  report:{
    overview:[{label:'Analysis',value:'multi_group_comparison'},{label:'Target',value:'Score'},{label:'Status',value:'COMPLETE'}],
    method:[{label:'Test',value:'One-way ANOVA'},{label:'Grouping Field',value:'Group'}],
    evidence:[{label:'P Value',value:'0.0020'},{label:'Eta Squared',value:'0.7200'}],
    findings:[],warnings:[]
  }
};

function slug(name){return name.replace(/[^a-z0-9]+/gi,'-').toLowerCase()}
async function noHorizontalOverflow(page,label){
  const d=await page.evaluate(()=>({innerWidth:window.innerWidth,html:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
  assert.ok(d.html<=d.innerWidth+2&&d.body<=d.innerWidth+2,`${label}: horizontal overflow inner=${d.innerWidth}, html=${d.html}, body=${d.body}`);
}
async function activeJourneyVisible(page,viewport,label){
  if(viewport.width>1050)return;
  const d=await page.evaluate(()=>{
    const list=document.querySelector('.journey-list');
    const active=list?.querySelector('.journey-step.active');
    if(!list||!active)return null;
    const lr=list.getBoundingClientRect(),ar=active.getBoundingClientRect();
    return {listLeft:lr.left,listRight:lr.right,activeLeft:ar.left,activeRight:ar.right,step:active.dataset.journeyStep};
  });
  assert.ok(d,`${viewport.name}/${label}: active journey step should exist`);
  assert.ok(d.activeLeft>=d.listLeft-1&&d.activeRight<=d.listRight+1,`${viewport.name}/${label}: active step ${d.step} must be visible inside horizontal journey`);
}
async function screenshot(page,viewport,label){
  await noHorizontalOverflow(page,`${viewport.name}/${label}`);
  await activeJourneyVisible(page,viewport,label);
  await page.screenshot({path:path.join(artifactDir,`${slug(viewport.name)}-${slug(label)}.png`),fullPage:true});
}
async function mockNetwork(page){
  await page.route('**/favicon.ico',route=>route.fulfill({status:204,body:''}));
  await page.route('https://cdn.jsdelivr.net/**',route=>route.fulfill({status:200,contentType:'application/javascript',body:'window.XLSX=window.XLSX||{};'}));
  await page.route(`${analyticsBase}/capabilities`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(capabilities)}));
  await page.route(`${analyticsBase}/recommend/feature-engineering`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(feRecommendationPayload)}));
  await page.route(`${analyticsBase}/analyze`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(analysisPayload)}));
}
async function runViewport(browser,viewport){
  const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height}});
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',err=>errors.push(`pageerror: ${err.message}`));
  page.on('console',msg=>{if(msg.type()==='error')errors.push(`console: ${msg.text()}`)});
  page.on('response',response=>{if(response.status()>=400&&!response.url().endsWith('/favicon.ico'))errors.push(`http ${response.status()}: ${response.url()}`)});
  await page.addInitScript(base=>{window.KU_ANALYTICS_API_BASE=base},analyticsBase);
  await mockNetwork(page);
  await page.goto(appURL,{waitUntil:'domcontentloaded'});
  await page.waitForSelector('#workspaceView');
  assert.strictEqual(await page.locator('.text-size-control').count(),1,`${viewport.name}: Product header should expose one text-size control`);
  assert.strictEqual(await page.locator('html').getAttribute('data-ku-text-size'),'comfortable',`${viewport.name}: Product should default to comfortable text size`);

  const shell=await page.evaluate(()=>({
    asidePosition:getComputedStyle(document.querySelector('aside')).position,
    journeyDisplay:getComputedStyle(document.querySelector('.journey-list')).display,
    asideWidth:document.querySelector('aside').getBoundingClientRect().width,
    viewport:innerWidth
  }));
  if(viewport.width>1050){
    assert.strictEqual(shell.asidePosition,'sticky',`${viewport.name}: desktop sidebar should be sticky`);
    assert.notStrictEqual(shell.journeyDisplay,'flex',`${viewport.name}: desktop journey should not be horizontal flex`);
  }else{
    assert.strictEqual(shell.asidePosition,'sticky',`${viewport.name}: narrow workflow should remain sticky below the Product header`);
    assert.strictEqual(shell.journeyDisplay,'flex',`${viewport.name}: narrow journey should be horizontal flex`);
    assert.ok(shell.asideWidth<=shell.viewport+1,`${viewport.name}: narrow navigation must fit viewport`);
  }

  await page.getByRole('button',{name:'Load demo'}).click();
  await page.waitForFunction(()=>document.getElementById('rows')?.textContent==='9');
  await screenshot(page,viewport,'start-loaded');

  await page.locator('[data-journey-step="profile"]').click();
  await page.waitForSelector('#variablesView:not(.hidden)');
  await screenshot(page,viewport,'profile');

  await page.locator('[data-journey-step="analyze"]').click();
  await page.waitForSelector('#aiAnalyticsView:not(.hidden)');
  await page.locator('[data-question-type="compare-groups"]').click();
  await page.locator('#analysisTarget').selectOption('Score');
  await screenshot(page,viewport,'analyze-compare-groups');

  await page.locator('#continuePrepare').click();
  await page.waitForSelector('#prepareGroupField');
  await page.locator('#prepareGroupField').selectOption('Group');
  await page.waitForFunction(()=>!document.getElementById('continueSetup')?.disabled);
  await screenshot(page,viewport,'prepare');

  await page.locator('#continueSetup').click();
  await page.waitForSelector('#runAnalysisBtn:not([disabled])');
  const setupText=await page.locator('#setupBody').innerText();
  assert.ok(setupText.includes('One-way ANOVA'),`${viewport.name}: backend capability metadata should render in Setup`);
  const technical=page.locator('.technical-run-spec');
  assert.strictEqual(await technical.evaluate(node=>node.open),false,`${viewport.name}: Technical Run Specification should be collapsed by default`);
  await screenshot(page,viewport,'setup');
  await page.locator('.technical-run-spec > summary').click();
  assert.ok((await technical.innerText()).includes('v0.4.0'),`${viewport.name}: opening Technical Run Specification should show backend version`);
  await page.locator('.technical-run-spec > summary').click();

  await page.locator('#runAnalysisBtn').click();
  await page.waitForSelector('.result-answer');
  assert.ok((await page.locator('.result-answer').innerText()).includes('One-way ANOVA'),`${viewport.name}: answer-first Results should render validated method`);
  assert.ok((await page.locator('#familyResultDetails').innerText()).includes('Group Summary'),`${viewport.name}: family-specific group summary should render`);
  await screenshot(page,viewport,'results');

  const headerMain=await page.evaluate(()=>{
    const header=document.querySelector('header').getBoundingClientRect();
    const main=document.querySelector('main').getBoundingClientRect();
    return {headerBottom:header.bottom,mainTop:main.top};
  });
  assert.ok(headerMain.mainTop>=0,`${viewport.name}: main content should remain reachable`);
  assert.deepStrictEqual(errors,[],`${viewport.name}: browser errors detected:\n${errors.join('\n')}`);
  await context.close();
}

(async()=>{
  assert.strictEqual(appEntry,'app.html','browser Product smoke must use app.html');
  const browser=await chromium.launch({headless:true});
  try{
    const viewports=[
      {name:'desktop-1440',width:1440,height:900},
      {name:'tablet-900',width:900,height:1000},
      {name:'mobile-390',width:390,height:844}
    ];
    for(const viewport of viewports)await runViewport(browser,viewport);
    console.log(`FRONTEND_VISUAL_SMOKE_OK (${appEntry})`);
  }finally{
    await browser.close();
  }
})().catch(err=>{console.error(err);process.exit(1)});
