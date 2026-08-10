/* KU Open Data Analytics v0.5.1 deployment hotfix */
(function(){
  const $=id=>document.getElementById(id);

  // Upgrade existing sidebar items to working navigation.
  const navs=[...document.querySelectorAll('aside .nav')];
  const byText=t=>navs.find(n=>n.textContent.trim()===t);
  const stats=byText('Descriptive Statistics'); if(stats) stats.onclick=()=>showWorkspaceSection('stats');
  const explore=byText('Explore & Visualize'); if(explore){explore.textContent='Explore & Visualize · soon';explore.classList.add('nav-disabled');explore.onclick=null;}
  const chiSoon=byText('Chi-square · soon'); if(chiSoon){chiSoon.textContent='Chi-square';chiSoon.onclick=()=>showAnalysisView('chisquare');}
  const regSoon=byText('Regression · soon'); if(regSoon){regSoon.textContent='Linear Regression';regSoon.onclick=()=>showAnalysisView('regression');}
  const advisorNav=byText('Analysis Advisor'); if(advisorNav) advisorNav.onclick=()=>showWorkspaceSection('advisor');

  // Add Analysis Guide entry.
  const learn=[...document.querySelectorAll('aside .label')].find(x=>x.textContent.trim()==='LEARN');
  if(learn && !byText('Analysis Guide')){
    const g=document.createElement('div');g.className='nav';g.textContent='Analysis Guide';g.onclick=showGuide;learn.parentNode.insertBefore(g,learn.nextSibling);
  }

  // Add stable IDs for workspace targets.
  const cards=[...document.querySelectorAll('#workspaceView .card')];
  const statsCard=cards.find(c=>c.querySelector('.head')?.textContent.trim()==='Descriptive statistics');if(statsCard)statsCard.id='statsCard';
  const advisorCard=cards.find(c=>c.querySelector('.head')?.textContent.trim()==='Analysis Advisor');if(advisorCard)advisorCard.id='advisorCard';

  // Add Analysis Guide view.
  const main=document.querySelector('main');
  if(main && !$('guideView')){
    const guide=document.createElement('section');guide.id='guideView';guide.className='hidden';guide.innerHTML=`
      <h1>Analysis Guide</h1><p class="lead">Start from your business question — you do not need to know the statistical test name first.</p>
      <section class="card"><div class="head">What would you like to learn from your data?</div><div class="body"><div class="guide-grid">
        <button class="guide-card" onclick="guideJump('describe')"><b>📊 What is happening?</b><span>Summarize typical values, distributions, or category shares.</span></button>
        <button class="guide-card" onclick="guideJump('relationship')"><b>🔗 Are two things related?</b><span>Check association between numeric or categorical variables.</span></button>
        <button class="guide-card" onclick="guideJump('compare')"><b>⚖️ Are groups really different?</b><span>Compare a target, two groups, matched data, or three or more groups.</span></button>
        <button class="guide-card" onclick="guideJump('regression')"><b>📈 How is an outcome related to several factors?</b><span>Explain a numeric outcome using one or more predictors.</span></button>
      </div></div></section>
      <section class="card" id="guideDescribe"><div class="head">1. What is happening?</div><div class="body"><div class="advisor"><b>Numeric variable</b> → Descriptive Statistics.<br><b>Categorical / ordinal variable</b> → Frequency Tables.</div><div class="row"><button class="btn" onclick="showWorkspaceSection('stats')">Open Descriptive Statistics</button><button class="btn" onclick="showAnalysisView('frequency')">Open Frequency Tables</button></div></div></section>
      <section class="card" id="guideRelationship"><div class="head">2. Are two things related?</div><div class="body"><div class="advisor"><b>Numeric × Numeric</b> → Pearson for roughly linear relationships; Spearman for ranked/ordinal or monotonic relationships.<br><b>Categorical × Categorical</b> → Chi-square.<br><br><b>Important:</b> association does not by itself prove causation.</div><div class="row"><button class="btn" onclick="showAnalysisView('correlation')">Open Correlation</button><button class="btn" onclick="showAnalysisView('chisquare')">Open Chi-square</button></div></div></section>
      <section class="card" id="guideCompare"><div class="head">3. Are groups really different?</div><div class="body"><div class="decision-tree"><div><b>Compare with a known target</b><span>→ One-sample t-test</span></div><div><b>Two independent groups</b><span>→ Welch independent-samples t-test</span></div><div><b>Before–after / matched observations</b><span>→ Paired-samples t-test</span></div><div><b>Three or more independent groups</b><span>→ One-way ANOVA</span></div></div><div class="row"><button class="btn" onclick="showAnalysisView('ttest')">Open t-tests</button><button class="btn" onclick="showAnalysisView('anova')">Open One-way ANOVA</button></div></div></section>
      <section class="card" id="guideRegression"><div class="head">4. How is an outcome related to several factors?</div><div class="body"><div class="advisor">Use <b>Linear Regression</b> when the outcome is numeric and you want to estimate its relationship with one or more numeric predictors. Regression can support explanation and, with proper validation, prediction. Coefficients do not automatically prove causality.</div><div class="row"><button class="btn" onclick="showAnalysisView('regression')">Open Linear Regression</button></div></div></section>
      <section class="card"><div class="head">Coming later</div><div class="body"><div class="advisor">Decision Trees, SPC / Control Charts, Design of Experiments (DoE), and additional predictive analytics are planned for future versions.</div></div></section>`;
    const analysis=$('analysisView');main.insertBefore(guide,analysis||null);
  }

  window.showGuide=function(){
    $('workspaceView')?.classList.add('hidden');$('variablesView')?.classList.add('hidden');$('analysisView')?.classList.add('hidden');$('guideView')?.classList.remove('hidden');
    document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));[...document.querySelectorAll('.nav')].find(n=>n.textContent.trim()==='Analysis Guide')?.classList.add('active');window.scrollTo({top:0,behavior:'smooth'});
  };
  window.guideJump=function(section){const map={describe:'guideDescribe',relationship:'guideRelationship',compare:'guideCompare',regression:'guideRegression'};$(map[section])?.scrollIntoView({behavior:'smooth',block:'start'});};
  window.showWorkspaceSection=function(section){if(typeof showView==='function')showView('workspace');$('guideView')?.classList.add('hidden');const card=$(section==='stats'?'statsCard':'advisorCard');if(card){card.scrollIntoView({behavior:'smooth',block:'center'});card.classList.add('flash-card');setTimeout(()=>card.classList.remove('flash-card'),1200);}};

  // Replace analysis navigation so a panel can be opened before loading data.
  const originalShowAnalysis=window.showAnalysisView;
  window.showAnalysisView=function(name){
    $('workspaceView')?.classList.add('hidden');$('variablesView')?.classList.add('hidden');$('guideView')?.classList.add('hidden');$('analysisView')?.classList.remove('hidden');
    document.querySelectorAll('.analysis-panel').forEach(p=>p.classList.add('hidden'));const panel=$(name+'Panel');
    if(!panel){alert('Analysis panel is unavailable. Please refresh the page.');return;}
    panel.classList.remove('hidden');if(window.headers?.length && typeof refreshAnalysisSelectors==='function')refreshAnalysisSelectors();
  };

  // Demo now uses the same parser/inference/render pipeline as uploaded data.
  window.demo=function(){
    const text=`Source,Group,Score,Age,Pre,Post,Satisfaction\nOnline,A,72,21,60,66,High\nStore,A,81,22,65,68,High\nOnline,A,77,24,70,74,Medium\nStore,A,85,23,68,72,High\nOnline,B,79,25,72,75,Medium\nStore,B,88,20,75,80,High\nOnline,B,88,20,64,68,High\nStore,B,91,22,69,72,High\nOnline,C,79,25,71,75,Medium\nStore,C,94,24,73,76,High\nOnline,C,86,23,76,80,High\nStore,C,90,26,78,82,Medium`;
    parseDelimited(text);$('paste').value=text;$('status').textContent='Demo dataset loaded';
  };

  // Add compact help to each implemented analysis.
  const help={
    frequency:['Use Frequency Tables for categorical or ordinal variables.','Select one variable, then use Count and Percent to understand how common each category is.'],
    ttest:['Use a t-test to compare a numeric outcome with a target, between two independent groups, or between matched measurements.','Read the mean difference and 95% CI first, then p-value and effect size. Inspect the Q–Q diagnostic.'],
    anova:['Use One-way ANOVA to compare a numeric outcome across three or more independent groups.','Read the omnibus F-test, effect size (η² / ω²), and Tukey–Kramer comparisons. Inspect boxplots and Brown–Forsythe.'],
    correlation:['Use correlation to examine whether two variables move together.','Pearson is for roughly linear numeric relationships; Spearman is rank-based. Correlation does not establish causation.'],
    chisquare:['Use Chi-square to test association between two categorical variables.','Read χ², p-value, Cramér’s V, and expected-count diagnostics.'],
    regression:['Use Linear Regression for a numeric outcome with one or more numeric predictors.','Interpret B coefficients with 95% CIs, R² / Adjusted R², and residual diagnostics. Coefficients do not automatically prove causality.']
  };
  Object.entries(help).forEach(([name,text])=>{const p=$(name+'Panel');if(!p||p.querySelector('.help-panel'))return;const d=document.createElement('details');d.className='help-panel';d.innerHTML=`<summary>How to use this analysis</summary><div class="help-body"><b>When to use</b><p>${text[0]}</p><b>How to interpret</b><p>${text[1]}</p><div class="help-footer"><button class="btn" onclick="showGuide()">Don’t know which test to use?</button></div></div>`;p.insertBefore(d,p.children[2]||null);});

  // Descriptive help.
  if(statsCard && !statsCard.querySelector('.help-panel')){const body=statsCard.querySelector('.body');const d=document.createElement('details');d.className='help-panel compact';d.innerHTML='<summary>How to use Descriptive Statistics</summary><div class="help-body"><b>When to use</b><p>Use this first to understand a numeric variable before formal tests.</p><b>What to look at</b><p>Mean is the arithmetic average; Median is more robust to skew/extreme values; SD describes spread; quartiles show the middle 50%.</p><div class="help-footer"><button class="btn" onclick="showGuide()">Open Analysis Guide</button></div></div>';body.insertBefore(d,body.firstChild);}

  // Startup health check.
  const health=document.createElement('div');health.id='systemHealth';health.className='system-health';main?.insertBefore(health,main.firstChild);
  window.addEventListener('load',()=>{const panels=['frequency','ttest','anova','chisquare','correlation','regression'].filter(x=>!$(x+'Panel'));const funcs=['runFrequency','runTTest','runAnova','runChiSquare','runCorrelation','runRegression'].filter(x=>typeof window[x]!=='function');if(panels.length||funcs.length){health.classList.add('error');health.innerHTML='<b>Startup self-check failed.</b> Some analysis modules did not load.';}else{health.classList.add('ok');health.innerHTML='<b>System check passed:</b> all implemented analysis modules are loaded.';}});
})();