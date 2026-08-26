// KU Open DA — Slice 7+8 multi-method execution, combined Results, and integration hardening.
(function(root,factory){
  const api=factory(root);
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.KUMultiMethod=api;
  if(root?.document){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>api.install());
    else api.install();
  }
})(typeof window!=='undefined'?window:globalThis,function(root){
'use strict';
const VERSION='1.0';
const ORDINAL_SEQUENCES=[
  ['low','medium','high'],
  ['poor','fair','good','very good','excellent'],
  ['strongly disagree','disagree','neutral','agree','strongly agree']
];
let installed=false,legacyWorkflow=null,mainObserver=null;
const unique=a=>[...new Set((Array.isArray(a)?a:[]).filter(Boolean))];
const missing=v=>v===''||v===null||v===undefined||(typeof v==='number'&&Number.isNaN(v));
const finite=v=>{if(missing(v))return null;const n=Number(v);return Number.isFinite(n)?n:null};
const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:NaN;
const variance=a=>{if(a.length<2)return NaN;const m=mean(a);return a.reduce((s,v)=>s+(v-m)**2,0)/(a.length-1)};
const sd=a=>Math.sqrt(variance(a));
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmt=(v,d=4)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
function clamp01(v){return Math.max(0,Math.min(1,v))}
function logGamma(z){
  const p=[676.5203681218851,-1259.1392167224028,771.32342877765313,-176.61502916214059,12.507343278686905,-.13857109526572012,9.9843695780195716e-6,1.5056327351493116e-7];
  if(z<.5)return Math.log(Math.PI)-Math.log(Math.sin(Math.PI*z))-logGamma(1-z);
  z-=1;let x=.99999999999980993;for(let i=0;i<p.length;i++)x+=p[i]/(z+i+1);const t=z+p.length-.5;return .5*Math.log(2*Math.PI)+(z+.5)*Math.log(t)-t+Math.log(x);
}
function betaFraction(a,b,x){
  const MAX=200,EPS=3e-14,FPMIN=1e-300;let qab=a+b,qap=a+1,qam=a-1,c=1,d=1-qab*x/qap;if(Math.abs(d)<FPMIN)d=FPMIN;d=1/d;let h=d;
  for(let m=1;m<=MAX;m++){
    let m2=2*m,aa=m*(b-m)*x/((qam+m2)*(a+m2));d=1+aa*d;if(Math.abs(d)<FPMIN)d=FPMIN;c=1+aa/c;if(Math.abs(c)<FPMIN)c=FPMIN;d=1/d;h*=d*c;
    aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2));d=1+aa*d;if(Math.abs(d)<FPMIN)d=FPMIN;c=1+aa/c;if(Math.abs(c)<FPMIN)c=FPMIN;d=1/d;const del=d*c;h*=del;if(Math.abs(del-1)<EPS)break;
  }
  return h;
}
function regularizedBeta(x,a,b){
  if(!Number.isFinite(x)||a<=0||b<=0)return NaN;if(x<=0)return 0;if(x>=1)return 1;
  const bt=Math.exp(logGamma(a+b)-logGamma(a)-logGamma(b)+a*Math.log(x)+b*Math.log(1-x));
  return x<(a+1)/(a+b+2)?bt*betaFraction(a,b,x)/a:1-bt*betaFraction(b,a,1-x)/b;
}
function studentTCdf(t,df){if(!Number.isFinite(t)||!(df>0))return NaN;const x=df/(df+t*t),ib=regularizedBeta(x,df/2,.5);return t>=0?1-.5*ib:.5*ib}
function twoSidedTP(t,df){return clamp01(2*(1-studentTCdf(Math.abs(t),df)))}
function fCdf(f,df1,df2){if(!(f>=0)||!(df1>0)||!(df2>0))return NaN;return regularizedBeta((df1*f)/(df1*f+df2),df1/2,df2/2)}
function fP(f,df1,df2){return clamp01(1-fCdf(f,df1,df2))}
function tCritical95(df){let lo=0,hi=20;for(let i=0;i<80;i++){const mid=(lo+hi)/2;if(studentTCdf(mid,df)<.975)lo=mid;else hi=mid}return(lo+hi)/2}
function pearson(x,y){
  if(x.length!==y.length||x.length<3)return NaN;const mx=mean(x),my=mean(y);let sxy=0,sxx=0,syy=0;for(let i=0;i<x.length;i++){const dx=x[i]-mx,dy=y[i]-my;sxy+=dx*dy;sxx+=dx*dx;syy+=dy*dy}return sxx>0&&syy>0?sxy/Math.sqrt(sxx*syy):NaN;
}
function ranks(values){
  const indexed=values.map((v,i)=>({v,i})).sort((a,b)=>a.v-b.v),out=Array(values.length);let i=0;
  while(i<indexed.length){let j=i+1;while(j<indexed.length&&indexed[j].v===indexed[i].v)j++;const r=(i+j-1)/2+1;for(let k=i;k<j;k++)out[indexed[k].i]=r;i=j}
  return out;
}
function spearman(x,y){return pearson(ranks(x),ranks(y))}
function correlationP(r,n){if(!Number.isFinite(r)||n<3)return NaN;if(Math.abs(r)>=1-1e-14)return 0;const t=r*Math.sqrt((n-2)/(1-r*r));return twoSidedTP(t,n-2)}
function recognizedOrdinalMapper(values){
  const observed=new Set(values.filter(v=>!missing(v)).map(v=>String(v).trim().toLowerCase()));if(observed.size<2)return null;
  for(const seq of ORDINAL_SEQUENCES){if([...observed].every(v=>seq.includes(v))){const order=seq.filter(v=>observed.has(v));return new Map(order.map((v,i)=>[v,i+1]))}}
  return null;
}
function numericColumns(matrix,target){
  return (matrix.columns||[]).filter(name=>name!==target).filter(name=>{const vals=(matrix.rows||[]).map(r=>r?.[name]).filter(v=>!missing(v));if(vals.length<3)return false;return vals.filter(v=>finite(v)!==null).length/vals.length>=.9});
}
function pairData(matrix,target,predictor,{rankTarget=false}={}){
  let mapper=null;if(rankTarget){const raw=(matrix.rows||[]).map(r=>r?.[target]).filter(v=>!missing(v));if(raw.some(v=>finite(v)===null)){mapper=recognizedOrdinalMapper(raw);if(!mapper)throw new Error(`Spearman correlation requires a recognized ordinal order for text target ${target}.`)}}
  const x=[],y=[];for(const row of matrix.rows||[]){const xv=finite(row?.[predictor]);let yv=finite(row?.[target]);if(yv===null&&mapper&&!missing(row?.[target]))yv=mapper.get(String(row[target]).trim().toLowerCase())??null;if(xv===null||yv===null)continue;x.push(xv);y.push(yv)}return{x,y};
}
function correlationResult(methodId,matrix,plan){
  const isSpearman=methodId==='spearman-correlation',predictors=numericColumns(matrix,plan.target),findings=[];
  for(const predictor of predictors){const pair=pairData(matrix,plan.target,predictor,{rankTarget:isSpearman});if(pair.x.length<3)continue;const r=isSpearman?spearman(pair.x,pair.y):pearson(pair.x,pair.y);if(!Number.isFinite(r))continue;findings.push({predictor,relationship:`${predictor} ↔ ${plan.target}`,effect:r,p_value:correlationP(r,pair.x.length),n:pair.x.length,interpretation:`${isSpearman?'Spearman ρ':'Pearson r'} = ${r.toFixed(4)}`})}
  findings.sort((a,b)=>Math.abs(b.effect)-Math.abs(a.effect));if(!findings.length)throw new Error(`No usable numeric predictor pairs are available for ${isSpearman?'Spearman':'Pearson'} correlation.`);
  return{status:'COMPLETE',route:'local_correlation',analysis_type:isSpearman?'spearman_correlation':'pearson_correlation',target:plan.target,mode:'local',method:{test:isSpearman?'Spearman rank correlation':'Pearson correlation',execution:'browser'},dataset:{rows:matrix.rows.length,columns:matrix.columns.length},evidence:{relationships_tested:findings.length,strongest_abs_correlation:Math.abs(findings[0].effect),strongest_predictor:findings[0].predictor},findings,warnings:['Pairwise association does not establish causal drivers.'],readiness:'LOCAL_EXECUTION_READY'};
}
function invertMatrix(A){
  const n=A.length,M=A.map((r,i)=>[...r,...Array.from({length:n},(_,j)=>i===j?1:0)]);for(let c=0;c<n;c++){let pivot=c;for(let r=c+1;r<n;r++)if(Math.abs(M[r][c])>Math.abs(M[pivot][c]))pivot=r;if(Math.abs(M[pivot][c])<1e-12)throw new Error('Regression design matrix is singular after collinearity screening.');[M[c],M[pivot]]=[M[pivot],M[c]];const d=M[c][c];for(let j=0;j<2*n;j++)M[c][j]/=d;for(let r=0;r<n;r++){if(r===c)continue;const f=M[r][c];for(let j=0;j<2*n;j++)M[r][j]-=f*M[c][j]}}
  return M.map(r=>r.slice(n));
}
function matMul(A,B){const rows=A.length,cols=B[0].length,k=B.length,out=Array.from({length:rows},()=>Array(cols).fill(0));for(let i=0;i<rows;i++)for(let t=0;t<k;t++)for(let j=0;j<cols;j++)out[i][j]+=A[i][t]*B[t][j];return out}
function transpose(A){return A[0].map((_,j)=>A.map(r=>r[j]))}
function independentPredictors(rows,names){
  const n=rows.length,basis=[Array(n).fill(1/Math.sqrt(n))],kept=[],dropped=[];
  for(const name of names){const original=rows.map(r=>r[name]),v=[...original];for(const b of basis){const dot=v.reduce((s,x,i)=>s+x*b[i],0);for(let i=0;i<n;i++)v[i]-=dot*b[i]}const norm=Math.sqrt(v.reduce((s,x)=>s+x*x,0)),origNorm=Math.sqrt(original.reduce((s,x)=>s+x*x,0));if(norm<=1e-10*Math.max(1,origNorm)){dropped.push(name);continue}basis.push(v.map(x=>x/norm));kept.push(name)}return{kept,dropped};
}
function olsResult(matrix,plan){
  const candidates=numericColumns(matrix,plan.target);if(!candidates.length)throw new Error('OLS requires at least one numeric predictor.');
  const complete=[];for(const row of matrix.rows||[]){const y=finite(row?.[plan.target]);if(y===null)continue;const obj={_y:y};let ok=true;for(const name of candidates){const v=finite(row?.[name]);if(v===null){ok=false;break}obj[name]=v}if(ok)complete.push(obj)}
  if(complete.length<4)throw new Error('OLS requires at least four complete observations.');
  const independent=independentPredictors(complete,candidates),names=independent.kept;if(!names.length)throw new Error('OLS found no non-constant independent numeric predictor.');const n=complete.length,k=names.length;if(n<=k+1)throw new Error(`OLS needs more complete observations than parameters; ${n} rows are available for ${k} predictors.`);
  const X=complete.map(r=>[1,...names.map(name=>r[name])]),Y=complete.map(r=>[r._y]),Xt=transpose(X),XtX=matMul(Xt,X),inv=invertMatrix(XtX),beta=matMul(matMul(inv,Xt),Y).map(r=>r[0]),pred=X.map(r=>r.reduce((s,v,j)=>s+v*beta[j],0)),y=complete.map(r=>r._y),my=mean(y),sse=y.reduce((s,v,i)=>s+(v-pred[i])**2,0),sst=y.reduce((s,v)=>s+(v-my)**2,0),ssr=Math.max(0,sst-sse),dfResid=n-k-1,mse=sse/dfResid,rmse=Math.sqrt(sse/n),r2=sst>0?1-sse/sst:NaN,adj=Number.isFinite(r2)?1-(1-r2)*(n-1)/dfResid:NaN,F=k>0&&mse>0?(ssr/k)/mse:NaN,modelP=Number.isFinite(F)?fP(F,k,dfResid):NaN,crit=tCritical95(dfResid);
  const findings=[];for(let j=1;j<beta.length;j++){const se=Math.sqrt(Math.max(0,mse*inv[j][j])),t=se>0?beta[j]/se:NaN,p=Number.isFinite(t)?twoSidedTP(t,dfResid):NaN;findings.push({predictor:names[j-1],coefficient:beta[j],standard_error:se,t,p_value:p,ci_low:beta[j]-crit*se,ci_high:beta[j]+crit*se,effect:Math.abs(beta[j]),interpretation:`B = ${beta[j].toFixed(4)}; p = ${Number.isFinite(p)?p.toFixed(4):'—'}`})}
  findings.sort((a,b)=>Math.abs(b.t||0)-Math.abs(a.t||0));const warnings=['OLS coefficients are conditional linear associations and do not establish causality.'];if(independent.dropped.length)warnings.push(`Exact/near-exact collinearity screening excluded: ${independent.dropped.join(', ')}.`);
  return{status:'COMPLETE',route:'local_regression',analysis_type:'ols_regression',target:plan.target,mode:'local',method:{model:'Ordinary Least Squares',execution:'browser',intercept:beta[0]},dataset:{rows:n,columns:k+1},evidence:{r2,adjusted_r2:adj,rmse,f:F,model_p_value:modelP,n,predictors_used:k,predictors_dropped:independent.dropped.length},findings,warnings,readiness:'LOCAL_EXECUTION_READY'};
}
function groupedNumeric(matrix,target,group){const map=new Map();for(const row of matrix.rows||[]){const y=finite(row?.[target]),g=row?.[group];if(y===null||missing(g))continue;const key=String(g);if(!map.has(key))map.set(key,[]);map.get(key).push(y)}return[...map.entries()].sort((a,b)=>a[0].localeCompare(b[0]))}
function welchResult(matrix,plan){
  const group=plan.preparation?.groupField;if(!group)throw new Error('Welch t-test requires a reviewed grouping field.');const groups=groupedNumeric(matrix,plan.target,group);if(groups.length!==2)throw new Error(`Welch t-test requires exactly 2 complete groups; found ${groups.length}.`);if(groups.some(([,v])=>v.length<2))throw new Error('Welch t-test requires at least 2 complete observations in each group.');
  const [[g1,a],[g2,b]]=groups,m1=mean(a),m2=mean(b),v1=variance(a),v2=variance(b),se=Math.sqrt(v1/a.length+v2/b.length),t=se>0?(m1-m2)/se:NaN,df=(v1/a.length+v2/b.length)**2/((v1/a.length)**2/(a.length-1)+(v2/b.length)**2/(b.length-1)),p=Number.isFinite(t)?twoSidedTP(t,df):NaN,sp=Math.sqrt(((a.length-1)*v1+(b.length-1)*v2)/(a.length+b.length-2)),J=1-3/(4*(a.length+b.length)-9),g=sp>0?J*(m1-m2)/sp:NaN;
  const summaries=groups.map(([name,v])=>({group:name,n:v.length,mean:mean(v),sd:sd(v)}));return{status:'COMPLETE',route:'local_group_comparison',analysis_type:'two_group_comparison',target:plan.target,mode:'local',method:{test:'Welch t-test',grouping_field:group,execution:'browser'},dataset:{rows:a.length+b.length,columns:2},evidence:{t,df,p_value:p,mean_difference:m1-m2,hedges_g:g,groups:2,n_total:a.length+b.length},group_summaries:summaries,findings:[],warnings:[],readiness:'LOCAL_EXECUTION_READY'};
}
function anovaResult(matrix,plan){
  const group=plan.preparation?.groupField;if(!group)throw new Error('One-way ANOVA requires a reviewed grouping field.');const groups=groupedNumeric(matrix,plan.target,group);if(groups.length<3)throw new Error(`One-way ANOVA requires 3 or more complete groups; found ${groups.length}.`);if(groups.some(([,v])=>v.length<2))throw new Error('One-way ANOVA requires at least 2 complete observations in every group.');
  const all=groups.flatMap(([,v])=>v),grand=mean(all),ssb=groups.reduce((s,[,v])=>s+v.length*(mean(v)-grand)**2,0),ssw=groups.reduce((s,[,v])=>{const m=mean(v);return s+v.reduce((q,x)=>q+(x-m)**2,0)},0),df1=groups.length-1,df2=all.length-groups.length,F=(ssb/df1)/(ssw/df2),p=fP(F,df1,df2),eta=(ssb+ssw)>0?ssb/(ssb+ssw):NaN,summaries=groups.map(([name,v])=>({group:name,n:v.length,mean:mean(v),sd:sd(v)}));
  return{status:'COMPLETE',route:'local_group_comparison',analysis_type:'multi_group_comparison',target:plan.target,mode:'local',method:{test:'One-way ANOVA',grouping_field:group,execution:'browser'},dataset:{rows:all.length,columns:2},evidence:{f:F,df_between:df1,df_within:df2,p_value:p,eta_squared:eta,groups:groups.length,n_total:all.length},group_summaries:summaries,findings:[],warnings:[],readiness:'LOCAL_EXECUTION_READY'};
}
function runLocalMethod(methodId,matrix,plan){if(methodId==='linear-regression')return olsResult(matrix,plan);if(methodId==='pearson-correlation'||methodId==='spearman-correlation')return correlationResult(methodId,matrix,plan);if(methodId==='welch-t-test')return welchResult(matrix,plan);if(methodId==='one-way-anova')return anovaResult(matrix,plan);throw new Error(`Local execution is not implemented for method ${methodId}.`)}
function localReport(method,result){
  const evidence=Object.entries(result.evidence||{}).filter(([,v])=>['number','string','boolean'].includes(typeof v)).slice(0,8).map(([k,v])=>({label:k.replaceAll('_',' '),value:typeof v==='number'?fmt(v):String(v)}));
  return{overview:[{label:'Analysis',value:method.label},{label:'Target',value:result.target||'Not required'},{label:'Execution',value:'Local · Browser'}],method:[{label:'Method',value:result.method?.test||result.method?.model||method.label},{label:'Engine',value:'Browser Statistical Computing Engine'}],evidence,findings:result.findings||[],warnings:result.warnings||[]};
}
function profileManifest(){const current=root.KUProfileInsights?.getManifest?.();if(current)return current;try{return root.KUProfileManifest?.fromGlobals?.({})||null}catch(_){return null}}
function methodCatalog(){return root.KUMethodSelection?.CATALOG||[]}
function planExecution(plan={}){
  const manifest=profileManifest(),suitable=root.KUMethodSelection?.suitableMethods?.({plan,manifest})||[],ids=root.KUMethodSelection?.effectiveMethodIds?.(plan,manifest)||[],lookup=new Map(suitable.map(m=>[m.id,m])),selected=ids.map(id=>lookup.get(id)).filter(Boolean),localMethods=selected.filter(m=>m.engine==='browser'),backendMethods=selected.filter(m=>m.engine==='backend');
  if(!selected.length)throw new Error('No compatible analytical method is selected for execution.');if(backendMethods.length>1)throw new Error('This execution coordinator currently supports one validated backend method per analytical route.');
  return{schema_version:'1.0',methods:selected,localMethods,backendMethods,local_count:localMethods.length,backend_count:backendMethods.length,selected_method_ids:selected.map(m=>m.id)};
}
function preparationSignature(preparation={}){
  const fe=preparation.featureEngineering||{},lineage=(fe.lineage||[]).map(x=>({output_field:x.output_field||null,source_fields:[...(x.source_fields||[])].sort(),operation:x.operation||null,parameters:x.parameters||{}})).sort((a,b)=>String(a.output_field).localeCompare(String(b.output_field)));
  return{groupField:preparation.groupField||null,featureEngineering:{status:fe.status||null,reviewed:Boolean(fe.reviewed),recommenderVersion:fe.recommenderVersion||null,selectedIds:[...(fe.selectedIds||[])].sort(),derivedFields:[...(fe.derivedFields||[])].sort(),lineage}};
}
function fieldMetadataForState(state,plan){const selected=new Set([plan.target,...(plan.predictors||[])].filter(Boolean));return(state.dataset?.fields||[]).filter(f=>selected.has(f.name)).map(f=>({name:f.name,storage:f.storage||null,level:f.level||null})).sort((a,b)=>a.name.localeCompare(b.name))}
function stable(value){if(Array.isArray(value))return`[${value.map(stable).join(',')}]`;if(value&&typeof value==='object'){return`{${Object.keys(value).sort().map(k=>`${JSON.stringify(k)}:${stable(value[k])}`).join(',')}}`}return JSON.stringify(value)}
function resultMatchesPlan(state={}){
  const snapshot=state.result?.planSnapshot,p=state.analysisPlan||{};if(!snapshot)return true;
  if(snapshot.questionType!==p.questionType||snapshot.target!==p.target||snapshot.route!==p.route||snapshot.methodMode!==(p.methodMode||'recommended'))return false;
  if(stable([...(snapshot.predictors||[])].sort())!==stable([...(p.predictors||[])].sort()))return false;
  if(stable([...(snapshot.selectedMethods||[])].sort())!==stable([...(p.selectedMethods||[])].sort()))return false;
  if(stable(preparationSignature(snapshot.preparation||{}))!==stable(preparationSignature(p.preparation||{})))return false;
  if(Number(snapshot.datasetRevision||0)!==Number(state.dataset?.revision||0))return false;
  if(stable((snapshot.fieldMetadata||[]).slice().sort((a,b)=>a.name.localeCompare(b.name)))!==stable(fieldMetadataForState(state,p)))return false;
  return true;
}
function rawRows(){try{return typeof data!=='undefined'&&Array.isArray(data)?data:[]}catch(_){return[]}}
function completeGroupCount(plan,rows=rawRows()){
  const group=plan.preparation?.groupField||root.document?.getElementById('prepareGroupField')?.value||null;if(!group||!plan.target)return 0;const groups=new Set();for(const row of rows){if(finite(row?.[plan.target])===null||missing(row?.[group]))continue;groups.add(String(row[group]))}return groups.size;
}
function methodPreparationBlockers(plan={},rows=rawRows()){
  let execution;try{execution=planExecution(plan)}catch(_){return[]}
  const ids=new Set(execution.selected_method_ids),blockers=[],count=completeGroupCount(plan,rows);
  if(ids.has('welch-t-test')&&plan.preparation?.groupField&&count!==2)blockers.push(`Welch t-test requires exactly 2 complete groups; ${count} are currently observed. Choose a compatible grouping field or method.`);
  if(ids.has('one-way-anova')&&plan.preparation?.groupField&&count<3)blockers.push(`One-way ANOVA requires 3 or more complete groups; ${count} are currently observed. Choose a compatible grouping field or method.`);
  return blockers;
}
function ensureStyles(){if(!root.document||root.document.querySelector('link[data-ku-multi-method]'))return;const link=root.document.createElement('link');link.rel='stylesheet';link.href='src/multi-method.css';link.dataset.kuMultiMethod='true';root.document.head.appendChild(link)}
function workflowHost(){let view=root.document?.getElementById('journeyPendingView');if(!view){view=root.document.createElement('section');view.id='journeyPendingView';root.document.querySelector('main')?.appendChild(view)}['workspaceView','variablesView','analysisView','aiAnalyticsView'].forEach(id=>root.document.getElementById(id)?.classList.add('hidden'));view.classList.remove('hidden');return view}
function currentBar(){return'<div class="current-analysis-bar" data-current-analysis></div>'}
function emitBar(){try{root.document.dispatchEvent(new CustomEvent('ku:render-current-analysis'))}catch(_){}}
function engineBadge(method){return method.engine==='browser'?'<span class="multi-engine browser">Local · Browser</span>':'<span class="multi-engine backend">KU Validated Engine</span>'}
function syncMethodPrepGate(){
  if(root.KUAppState?.getState?.().currentStep!=='prepare')return;const p=root.KUAppState.getState().analysisPlan,view=root.document.getElementById('journeyPendingView'),footer=view?.querySelector('.workflow-footer');if(!view||!footer)return;const blockers=methodPreparationBlockers(p);let box=view.querySelector('#methodPrepBlockers');if(blockers.length){if(!box){box=root.document.createElement('div');box.id='methodPrepBlockers';box.className='workflow-blocker method-prep-blocker';footer.before(box)}box.innerHTML=`<b>Selected method needs preparation review</b>${blockers.map(x=>`<p>${safe(x)}</p>`).join('')}`}else box?.remove();const button=root.document.getElementById('continueSetup');if(!button)return;const baseBlocked=Boolean(root.document.getElementById('prepBlockers')?.classList.contains('workflow-blocker')),fe=root.KUFeatureEngineeringReview,feReady=fe?.isApprovalReady?fe.isApprovalReady(p):!button.disabled;button.disabled=baseBlocked||blockers.length>0||!feReady;
}
function capabilityRows(cap){if(!cap)return'';const rows=[['Intent',cap.intent],['Validation',cap.validation],...Object.entries(cap.policy||{}).map(([k,v])=>[k,typeof v==='object'?JSON.stringify(v):v]),...Object.entries(cap.preparation||{}).map(([k,v])=>[`Preparation: ${k}`,v])];return rows.map(([k,v])=>`<div class="setup-kv"><span>${safe(String(k).replaceAll('_',' '))}</span><b>${safe(v)}</b></div>`).join('')}
function setupMethodList(execution){return`<div class="multi-setup-methods">${execution.methods.map(m=>`<div class="multi-setup-method"><div><b>${safe(m.label)}</b><span>${safe(m.summary||'')}</span></div>${engineBadge(m)}</div>`).join('')}</div>`}
async function renderSetup(){
  const view=workflowHost(),p=root.KUAppState.getState().analysisPlan;let execution;try{execution=planExecution(p)}catch(error){view.innerHTML=`<div class="step-kicker">STEP 5 · SETUP</div><h1>How Will the Analysis Run?</h1><div class="workflow-blocker"><b>Execution plan unavailable</b><p>${safe(error.message)}</p></div>`;return}
  view.innerHTML=`<div class="step-kicker">STEP 5 · SETUP</div><h1>How Will the Analysis Run?</h1><p class="lead">Confirm how each selected method will execute. Local statistical methods stay in your browser; validated model methods use the KU backend.</p>${currentBar()}<section class="card"><div class="head">Selected Methods</div><div class="body" id="multiSetupBody"><div class="empty">Preparing execution plan…</div></div></section><div class="workflow-footer"><button class="btn ghost" onclick="goToJourneyStep('prepare')">← Back to Prepare</button><button id="runAnalysisBtn" class="btn primary" disabled>Run selected method${execution.methods.length===1?'':'s'} →</button></div>`;emitBar();
  try{
    let caps=null,cap=null;if(execution.backend_count){caps=await legacyWorkflow.loadCapabilities();cap=caps.routes?.[p.route];if(!cap)throw new Error(`Backend capability metadata does not include route ${p.route}.`)}
    const fields=root.KUAnalyticsClient?.selectedCsvFields?.(p)||[],derived=p.preparation?.featureEngineering?.derivedFields||[],serviceVersion=caps?.service?.version||null,backendCalls=execution.backend_count?1:0;
    root.document.getElementById('multiSetupBody').innerHTML=`<div class="setup-grid"><div class="setup-hero"><span>Execution plan</span><b>${execution.methods.length} selected method${execution.methods.length===1?'':'s'}</b><small>${execution.local_count} local · ${execution.backend_count} KU Validated Engine</small></div><div class="setup-kv"><span>Target</span><b>${safe(p.target||'Not required')}</b></div><div class="setup-kv"><span>Original predictors / inputs</span><b>${(p.predictors||[]).length}</b></div><div class="setup-kv"><span>Derived fields</span><b>${derived.length?safe(derived.join(', ')):'None selected'}</b></div></div>${setupMethodList(execution)}${cap?`<div class="setup-policy">${capabilityRows(cap)}</div>`:'<div class="multi-local-note"><b>Local-only execution</b><span>No POST /analyze model call is required for this selected method set. Aggregated Profile/FE intelligence requests remain separate from analysis execution.</span></div>'}<details class="technical-run-spec"><summary>Technical Run Specification</summary><div class="body"><div class="setup-kv"><span>Backend API</span><b>${backendCalls?(serviceVersion?`v${safe(serviceVersion)}`:'Configured backend'):'Not required for local execution'}</b></div><div class="setup-kv"><span>Backend /analyze calls planned</span><b>${backendCalls}</b></div><div class="setup-kv"><span>Local methods</span><b>${execution.local_count}</b></div><div class="setup-kv"><span>Backend methods</span><b>${execution.backend_count}</b></div><div class="setup-kv"><span>Fields prepared</span><b>${safe(fields.join(', '))}</b></div><div class="setup-kv"><span>Prepared matrix contract</span><b>${p.preparation?.featureEngineering?.reviewed?'Browser FE Manifest v1':'Legacy compatibility'}</b></div></div></details>`;
    root.KUAppState.setSetup({mode:p.methodMode||'recommended',confirmed:false,configuration:{selectedMethods:execution.selected_method_ids,localMethods:execution.localMethods.map(m=>m.id),backendMethods:execution.backendMethods.map(m=>m.id),backendAnalysisCalls:backendCalls,executionFields:fields,serviceVersion}});
    const button=root.document.getElementById('runAnalysisBtn');button.disabled=false;button.addEventListener('click',async()=>{button.disabled=true;button.textContent=`Running ${execution.methods.length===1?'analysis':'selected methods'}…`;root.KUAppState.setSetup({confirmed:true});try{await runSelected(p);root.goToJourneyStep('results')}catch(error){button.disabled=false;button.textContent=`Run selected method${execution.methods.length===1?'':'s'} →`;root.document.getElementById('multiSetupBody')?.insertAdjacentHTML('beforeend',`<div class="workflow-blocker"><b>Analysis could not run</b><p>${safe(error.message)}</p></div>`)}});
  }catch(error){root.document.getElementById('multiSetupBody').innerHTML=`<div class="workflow-blocker"><b>Execution metadata unavailable</b><p>${safe(error.message)}</p></div>`}
}
function backendSummary(r){const e=r?.evidence||{};if(r?.route==='regression')return`R² ${fmt(e.r2,3)}, RMSE ${fmt(e.rmse,3)}, MAE ${fmt(e.mae,3)}`;if(r?.route==='classification'&&r.analysis_type==='binary')return`ROC-AUC ${fmt(e.roc_auc,3)}, PR-AUC ${fmt(e.pr_auc,3)}, F1 ${fmt(e.f1,3)}`;if(r?.route==='classification'&&r.analysis_type==='multiclass')return`Macro F1 ${fmt(e.macro_f1,3)}, balanced accuracy ${fmt(e.balanced_accuracy,3)}`;if(r?.route==='segmentation')return`Silhouette ${fmt(e.silhouette,3)}`;if(r?.route==='association')return`${e.practical_supported??0} practically supported relationships`;if(r?.route==='compare_groups')return`${r.method?.test||'Group comparison'}, p ${Number(e.p_value)<.001?'< .001':fmt(e.p_value,4)}`;return r?.status||'COMPLETE'}
function localSummary(r){const e=r?.evidence||{};if(r?.analysis_type==='ols_regression')return`OLS R² ${fmt(e.r2,3)}, adjusted R² ${fmt(e.adjusted_r2,3)}, RMSE ${fmt(e.rmse,3)}`;if(String(r?.analysis_type).includes('correlation'))return`${e.relationships_tested??0} relationships tested; strongest |association| ${fmt(e.strongest_abs_correlation,3)}`;if(r?.analysis_type==='two_group_comparison')return`Welch p ${fmt(e.p_value,4)}, Hedges g ${fmt(e.hedges_g,3)}`;if(r?.analysis_type==='multi_group_comparison')return`ANOVA p ${fmt(e.p_value,4)}, η² ${fmt(e.eta_squared,3)}`;return r?.status||'COMPLETE'}
async function runSelected(plan){
  const execution=planExecution(plan),matrix=root.KUAnalyticsClient?.analyticalDataset?.(plan);if(!matrix)throw new Error('Prepared analytical matrix is unavailable.');const methods=[];
  for(const method of execution.localMethods){try{const result=runLocalMethod(method.id,matrix,plan);methods.push({id:method.id,label:method.label,engine:'browser',engine_label:'Local · Browser',validated_backend:false,status:'COMPLETE',result,report:localReport(method,result)})}catch(error){methods.push({id:method.id,label:method.label,engine:'browser',engine_label:'Local · Browser',validated_backend:false,status:'ERROR',error:error?.message||String(error)})}}
  for(const method of execution.backendMethods){try{const payload=await root.KUAnalyticsClient.runPlan(plan);methods.push({id:method.id,label:method.label,engine:'backend',engine_label:'KU Validated Engine',validated_backend:true,status:'COMPLETE',result:payload.result,report:payload.report})}catch(error){methods.push({id:method.id,label:method.label,engine:'backend',engine_label:'KU Validated Engine',validated_backend:true,status:'ERROR',error:error?.message||String(error)})}}
  const completed=methods.filter(m=>m.status==='COMPLETE');if(!completed.length)throw new Error(methods.map(m=>`${m.label}: ${m.error||'failed'}`).join(' | '));const recommended=execution.methods.find(m=>m.recommended),primary=completed.find(m=>m.id===recommended?.id)||completed.find(m=>m.engine==='backend')||completed[0];
  const combined={schema_version:'multi_method_results_v1',execution:{coordinator_version:VERSION,requested_method_ids:execution.selected_method_ids,completed_method_ids:completed.map(m=>m.id),failed_method_ids:methods.filter(m=>m.status!=='COMPLETE').map(m=>m.id),local_count:execution.local_count,backend_count:execution.backend_count,backend_analysis_calls:execution.backend_count?1:0,execution_fields:[...(matrix.columns||[])],browser_feature_engineering:matrix.manifest||null,generated_at:new Date().toISOString()},methods,primary_method_id:primary.id,result:primary.result,report:primary.report};root.KUAppState.setResultPayload(combined,{validated:true,source:'multi-method'});return combined;
}
function scalarMetrics(result){return Object.entries(result?.evidence||{}).filter(([,v])=>['number','string','boolean'].includes(typeof v)).slice(0,8)}
function metricsHtml(result){return`<div class="result-metrics">${scalarMetrics(result).map(([k,v])=>`<div class="result-metric"><span>${safe(k.replaceAll('_',' '))}</span><b>${typeof v==='number'?(Number.isInteger(v)?v:fmt(v,4)):safe(v)}</b></div>`).join('')}</div>`}
function detailTable(result){
  if(result?.analysis_type==='ols_regression'&&(result.findings||[]).length)return`<div class="multi-detail-table"><table><thead><tr><th>Predictor</th><th>B</th><th>SE</th><th>t</th><th>p</th><th>95% CI</th></tr></thead><tbody>${result.findings.slice(0,12).map(x=>`<tr><td>${safe(x.predictor)}</td><td>${fmt(x.coefficient)}</td><td>${fmt(x.standard_error)}</td><td>${fmt(x.t)}</td><td>${fmt(x.p_value)}</td><td>${fmt(x.ci_low)} to ${fmt(x.ci_high)}</td></tr>`).join('')}</tbody></table></div>`;
  if(String(result?.analysis_type||'').includes('correlation')&&(result.findings||[]).length)return`<div class="multi-detail-table"><table><thead><tr><th>Predictor</th><th>Effect</th><th>p</th><th>N</th></tr></thead><tbody>${result.findings.slice(0,12).map(x=>`<tr><td>${safe(x.predictor)}</td><td>${fmt(x.effect)}</td><td>${fmt(x.p_value)}</td><td>${x.n}</td></tr>`).join('')}</tbody></table></div>`;
  if((result?.group_summaries||[]).length)return`<div class="multi-detail-table"><table><thead><tr><th>Group</th><th>N</th><th>Mean</th><th>SD</th></tr></thead><tbody>${result.group_summaries.map(x=>`<tr><td>${safe(x.group)}</td><td>${x.n}</td><td>${fmt(x.mean)}</td><td>${fmt(x.sd)}</td></tr>`).join('')}</tbody></table></div>`;return'';
}
function confusionHtml(r){const e=r?.evidence||{};if(!['tn','fp','fn','tp'].every(k=>Number.isFinite(Number(e[k]))))return'';return`<section class="card"><div class="head">Confusion matrix · primary method</div><div class="body"><div class="confusion"><div class="cm-corner"></div><div class="cm-head">Predicted −</div><div class="cm-head">Predicted +</div><div class="cm-head">Actual −</div><div class="cm-cell correct"><b>${e.tn}</b><span>TN</span></div><div class="cm-cell error"><b>${e.fp}</b><span>FP</span></div><div class="cm-head">Actual +</div><div class="cm-cell error"><b>${e.fn}</b><span>FN</span></div><div class="cm-cell correct"><b>${e.tp}</b><span>TP</span></div></div></div></section>`}
function renderCombinedResults(){
  const state=root.KUAppState.getState(),payload=state.result?.payload||{},view=workflowHost(),methods=Array.isArray(payload.methods)?payload.methods:[];if(!methods.length){legacyWorkflow.renderResults();return}const complete=methods.filter(m=>m.status==='COMPLETE'),primary=methods.find(m=>m.id===payload.primary_method_id&&m.status==='COMPLETE')||complete[0],current=resultMatchesPlan(state),localCount=complete.filter(m=>m.engine==='browser').length,backendCount=complete.filter(m=>m.engine==='backend').length,primarySummary=primary?(primary.engine==='backend'?backendSummary(primary.result):localSummary(primary.result)):'No completed method';
  view.innerHTML=`<div class="step-kicker">STEP 6 · RESULTS</div><h1>Understand the Results</h1><p class="lead">Review the combined evidence from every selected method. Each result retains its execution source and methodological scope.</p>${currentBar()}${current?'':`<div class="result-stale"><b>Previous result</b><span>This result was generated from an earlier predictor, method, field metadata, or preparation selection. It is preserved for comparison; return to Setup and run again to refresh it.</span></div>`}<section class="result-answer"><span>Answer</span><h2>${complete.length===1?safe(primarySummary):`${complete.length} selected methods completed · ${localCount} local + ${backendCount} KU Validated Engine`}</h2><p>${complete.length>1?`Primary method: ${safe(primary?.label||'—')} · ${safe(primarySummary)}.`:`${safe(primary?.label||'Selected method')} · ${safe(primary?.engine_label||'')}.`}</p></section><section class="card multi-execution-summary"><div class="head">Execution Summary</div><div class="body"><div class="result-metrics"><div class="result-metric"><span>Methods requested</span><b>${methods.length}</b></div><div class="result-metric"><span>Completed</span><b>${complete.length}</b></div><div class="result-metric"><span>Local browser</span><b>${localCount}</b></div><div class="result-metric"><span>Backend analysis calls</span><b>${payload.execution?.backend_analysis_calls??backendCount}</b></div></div></div></section><div class="multi-result-list">${methods.map(m=>`<section class="card multi-result-method ${m.status==='ERROR'?'failed':''}"><div class="head"><span>${safe(m.label)}</span>${m.engine==='browser'?'<span class="multi-engine browser">Local · Browser</span>':'<span class="multi-engine backend">KU Validated Engine</span>'}</div><div class="body">${m.status==='ERROR'?`<div class="workflow-blocker"><b>Method did not complete</b><p>${safe(m.error||'Unknown execution error')}</p></div>`:`<p class="multi-method-summary">${safe(m.engine==='backend'?backendSummary(m.result):localSummary(m.result))}</p>${metricsHtml(m.result)}${detailTable(m.result)}${(m.result?.warnings||[]).length?`<div class="multi-method-warnings">${m.result.warnings.map(w=>`<p>${safe(w)}</p>`).join('')}</div>`:''}`}</div></section>`).join('')}</div>${confusionHtml(payload.result)}<section class="card"><div class="head">Primary Interpretation Report</div><div class="body" id="workflowReport"></div></section><details class="card result-technical"><summary>Technical result / combined payload</summary><div class="body"><pre>${safe(JSON.stringify(payload,null,2))}</pre></div></details><div class="workflow-footer"><button class="btn ghost" onclick="goToJourneyStep('analyze')">← Review Analysis Plan</button><button class="btn primary" onclick="goToJourneyStep('setup')">Run Again / Review Setup</button></div>`;
  if(primary?.report)root.KUAnalyticsClient?.renderExecutiveReport?.(primary.report,root.document.getElementById('workflowReport'));emitBar();
}
function wrappedShow(step){if(step==='prepare'){legacyWorkflow.show(step);setTimeout(syncMethodPrepGate,0);return}if(step==='setup'){renderSetup();return}if(step==='results'){const payload=root.KUAppState?.getState?.().result?.payload;if(Array.isArray(payload?.methods))renderCombinedResults();else legacyWorkflow.show(step);return}legacyWorkflow.show(step)}
function install(){
  if(installed||!root.document)return;if(!root.KUWorkflowSteps){setTimeout(install,0);return}installed=true;ensureStyles();legacyWorkflow=root.KUWorkflowSteps;root.KUWorkflowSteps=Object.freeze({show:wrappedShow,renderPrepare:legacyWorkflow.renderPrepare,renderSetup,renderResults:renderCombinedResults,loadCapabilities:legacyWorkflow.loadCapabilities});
  root.document.addEventListener('ku:statechange',()=>queueMicrotask(syncMethodPrepGate));root.document.addEventListener('click',event=>{if(!event.target.closest?.('#continueSetup'))return;if(root.KUAppState?.getState?.().currentStep!=='prepare')return;const blockers=methodPreparationBlockers(root.KUAppState.getState().analysisPlan);if(blockers.length){event.preventDefault();event.stopImmediatePropagation();syncMethodPrepGate()}},true);
  const main=root.document.querySelector('main');if(main&&typeof MutationObserver!=='undefined'){mainObserver=new MutationObserver(()=>queueMicrotask(syncMethodPrepGate));mainObserver.observe(main,{childList:true,subtree:true})}
  syncMethodPrepGate();
}
return Object.freeze({VERSION,logGamma,regularizedBeta,studentTCdf,fCdf,pearson,spearman,correlationP,runLocalMethod,olsResult,correlationResult,welchResult,anovaResult,planExecution,preparationSignature,resultMatchesPlan,methodPreparationBlockers,runSelected,renderSetup,renderCombinedResults,install});
});
