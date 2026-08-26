// KU Open DA — family-specific Step 6 details from validated payloads.
(function(root){
'use strict';
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
const pct=(v,d=1)=>Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(d)}%`:'—';
const has=v=>Number.isFinite(Number(v));
function card(title,body,cls=''){const s=document.createElement('section');s.className=`card result-family-detail ${cls}`.trim();s.innerHTML=`<div class="head">${safe(title)}</div><div class="body">${body}</div>`;return s}
function table(headers,rows){return `<div class="table"><table><thead><tr>${headers.map(h=>`<th>${safe(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(v=>`<td>${safe(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`}
function regressionTargetCoding(r){const enc=r.method?.target_encoding;if(enc?.type!=='ordinal_rank'||!enc.mapping)return null;const rows=Object.entries(enc.mapping).map(([label,rank])=>[label,rank]);return card('Target Coding',`<p class="result-coding-note">The ordinal target was encoded as ordered ranks for modeling. Rank order is meaningful; equal spacing between adjacent categories is not established by the coding.</p>${table(['Category','Rank'],rows)}`)}
function emphasizeOrdinalAnswer(r){if(r.route!=='regression'||r.method?.target_encoding?.type!=='ordinal_rank')return;const answer=document.querySelector('.result-answer h2');if(answer&&!answer.textContent.startsWith('Ordinal rank-coded target · '))answer.textContent=`Ordinal rank-coded target · ${answer.textContent}`}
function metadataSignature(fields=[]){return JSON.stringify(fields.map(f=>({name:f.name,storage:f.storage||null,level:f.level||null})).sort((a,b)=>String(a.name).localeCompare(String(b.name))))}
function ensureMetadataFreshness(state){
  const snapshot=state.result?.planSnapshot;
  if(!Array.isArray(snapshot?.fieldMetadata))return;
  const selected=new Set([state.analysisPlan?.target,...(state.analysisPlan?.predictors||[])].filter(Boolean));
  const current=(state.dataset?.fields||[]).filter(f=>selected.has(f.name));
  if(metadataSignature(snapshot.fieldMetadata)===metadataSignature(current)||document.querySelector('.result-stale'))return;
  const answer=document.querySelector('.result-answer');if(!answer)return;
  const banner=document.createElement('div');banner.className='result-stale';banner.innerHTML='<b>Previous validated result</b><span>Field storage or measurement metadata changed after this result was generated. The previous result is preserved for comparison; review Prepare and Setup, then run again to refresh it.</span>';
  answer.insertAdjacentElement('beforebegin',banner);
}
function segmentation(r){const f=r.findings;if(!f||Array.isArray(f)||typeof f!=='object')return null;const rows=Object.entries(f).map(([segment,x])=>[segment,`${num(x?.size_pct,1)}%`,(x?.high||[]).join(', ')||'—',(x?.low||[]).join(', ')||'—']);return rows.length?card('Segment Profiles',table(['Segment','Size','Higher than overall','Lower than overall'],rows)) : null}
function associations(r){const f=Array.isArray(r.findings)?r.findings:[];if(!f.length)return null;const rows=f.slice(0,12).map(x=>[x.relationship||x.title||'Relationship',num(x.effect,3),Number.isFinite(Number(x.q_value))?num(x.q_value,4):'—',x.interpretation||x.subtitle||'']);return card('Top Supported Associations',table(['Relationship','Effect','q-value','Interpretation'],rows))}
function groupSummary(r){const f=Array.isArray(r.group_summaries)?r.group_summaries:[];if(!f.length)return null;const rows=f.map(x=>[x.group,x.n,num(x.mean),x.sd===null?'—':num(x.sd)]);return card('Group Summary',table(['Group','N','Mean','SD'],rows))}
function warnings(r){const w=Array.isArray(r.warnings)?r.warnings.filter(Boolean):[];if(!w.length)return null;return card('Warnings / Guardrails',w.map(x=>`<p class="result-warning-item">⚠ ${safe(x)}</p>`).join(''),'result-warning-card')}
function recommendations(r){const list=Array.isArray(r.recommendations)?r.recommendations:[];if(!list.length)return null;return card('Recommended Follow-up',list.map(x=>`<div class="result-recommendation"><b>${safe(x.analysis||'Follow-up')}</b><span>${safe(x.reason||'')}</span></div>`).join(''))}
function resultKind(r){
  if(r.route==='classification'&&r.analysis_type==='binary')return'binary';
  if(r.route==='classification'&&r.analysis_type==='multiclass')return'multiclass';
  if(r.route==='compare_groups')return'compare';
  return r.route||'';
}
function metricPriority(r){
  const k=resultKind(r);
  if(k==='regression')return['r2','rmse','mae','mape','n','cv_r2'];
  if(k==='binary')return['roc_auc','pr_auc','f1','precision','recall','specificity','accuracy','balanced_accuracy'];
  if(k==='multiclass')return['macro_f1','weighted_f1','balanced_accuracy','roc_auc','log_loss','coverage','abstention_rate'];
  if(k==='segmentation')return['silhouette','n_clusters','pca_variance','calinski_harabasz','davies_bouldin'];
  if(k==='association')return['practical_supported','tested_pairs','significant_after_adjustment','max_effect'];
  if(k==='compare')return['p_value','hedges_g','eta_squared','mean_difference','n'];
  return[];
}
function metricLabel(k){return ({r2:'R²',rmse:'RMSE',mae:'MAE',mape:'MAPE',roc_auc:'ROC-AUC',pr_auc:'PR-AUC',f1:'F1',macro_f1:'Macro F1',weighted_f1:'Weighted F1',balanced_accuracy:'Balanced accuracy',log_loss:'Log loss',pca_variance:'PCA variance retained',silhouette:'Silhouette',p_value:'p-value',hedges_g:'Hedges g',eta_squared:'η²',practical_supported:'Supported relationships',tested_pairs:'Pairs tested',significant_after_adjustment:'Adjusted-significant',abstention_rate:'Abstention rate'})[k]||k.replaceAll('_',' ')}
function metricDisplay(k,v){
  if(!has(v))return String(v??'—');
  if(['pca_variance','coverage','abstention_rate'].includes(k))return pct(v);
  if(k==='p_value')return Number(v)<.001?'< .001':num(v,4);
  if(Number.isInteger(Number(v)))return String(v);
  return num(v,3);
}
function enhanceEvidence(r){
  const answer=document.querySelector('.result-answer');if(!answer)return;
  const evidence=r.evidence||{},preferred=metricPriority(r).filter(k=>Object.prototype.hasOwnProperty.call(evidence,k));
  const cards=[...document.querySelectorAll('#journeyPendingView > .card')];
  const keyCard=cards.find(x=>x.querySelector(':scope > .head')?.textContent.trim()==='Key evidence');
  if(!keyCard||!preferred.length)return;
  const shown=preferred.slice(0,4),rest=Object.keys(evidence).filter(k=>!shown.includes(k)&&['number','string','boolean'].includes(typeof evidence[k]));
  const body=keyCard.querySelector(':scope > .body');if(!body)return;
  body.innerHTML=`<div class="result-metrics result-metrics-priority">${shown.map(k=>`<div class="result-metric result-metric-priority"><span>${safe(metricLabel(k))}</span><b>${safe(metricDisplay(k,evidence[k]))}</b></div>`).join('')}</div>${rest.length?`<details class="result-evidence-more"><summary>View all validated evidence</summary><div class="result-metrics">${rest.map(k=>`<div class="result-metric"><span>${safe(metricLabel(k))}</span><b>${safe(metricDisplay(k,evidence[k]))}</b></div>`).join('')}</div></details>`:''}`;
}
function interpretation(r,state){
  const e=r.evidence||{},target=state.analysisPlan?.target||r.target||'the outcome',k=resultKind(r),items=[];
  if(k==='regression'){
    if(has(e.r2))items.push(`<b>Explained variation</b><span>The validated model accounts for approximately ${pct(e.r2)} of variation in ${safe(target)} on the reported validation evidence.</span>`);
    if(has(e.mae))items.push(`<b>Typical absolute error</b><span>Predictions differ from observed ${safe(target)} by about ${num(e.mae)} units on average, using MAE.</span>`);
    if(has(e.rmse))items.push(`<b>Larger misses matter</b><span>RMSE is ${num(e.rmse)}; compare this with the practical scale of ${safe(target)} before using predictions operationally.</span>`);
  }else if(k==='binary'){
    if(has(e.recall)&&has(e.precision))items.push(`<b>At the validated threshold</b><span>Recall is ${pct(e.recall)} and precision is ${pct(e.precision)}. This describes the trade-off between finding positive cases and how often positive predictions are correct.</span>`);
    if(has(e.roc_auc))items.push(`<b>Ranking ability</b><span>ROC-AUC is ${num(e.roc_auc)}, summarizing how well the model separates the two classes across thresholds.</span>`);
    if(has(e.pr_auc))items.push(`<b>Positive-class evidence</b><span>PR-AUC is ${num(e.pr_auc)} and is especially useful when the positive class is relatively uncommon.</span>`);
  }else if(k==='multiclass'){
    if(has(e.macro_f1))items.push(`<b>Across classes</b><span>Macro F1 is ${num(e.macro_f1)}, giving each class equal weight when summarizing classification performance.</span>`);
    if(has(e.balanced_accuracy))items.push(`<b>Class-balanced accuracy</b><span>Balanced accuracy is ${num(e.balanced_accuracy)}, reducing the influence of class-size imbalance.</span>`);
    if(has(e.coverage))items.push(`<b>Coverage</b><span>The model returns a class decision for ${pct(e.coverage)} of evaluated cases under the validated policy.</span>`);
  }else if(k==='segmentation'){
    if(has(e.silhouette))items.push(`<b>Segment separation</b><span>Silhouette is ${num(e.silhouette)}. Use the segment profiles below to judge whether the statistical separation is also operationally meaningful.</span>`);
    if(has(e.pca_variance))items.push(`<b>Information retained</b><span>The PCA representation retained ${pct(e.pca_variance)} of variance before clustering.</span>`);
  }else if(k==='association'){
    if(has(e.practical_supported))items.push(`<b>Supported leads</b><span>${Number(e.practical_supported)} relationship${Number(e.practical_supported)===1?'':'s'} met the backend's practical-support criteria. Treat them as evidence for follow-up, not as causal effects.</span>`);
  }else if(k==='compare'){
    if(has(e.p_value))items.push(`<b>Evidence of group difference</b><span>${Number(e.p_value)<.05?'The reported test provides statistical evidence of a group difference at the conventional 0.05 level.':'The reported test does not provide statistical evidence of a group difference at the conventional 0.05 level.'}</span>`);
    if(has(e.hedges_g))items.push(`<b>Effect size</b><span>Hedges g is ${num(e.hedges_g)}; interpret its practical importance together with the group means below.</span>`);
    if(has(e.eta_squared))items.push(`<b>Effect size</b><span>η² is ${num(e.eta_squared)}, the reported proportion of outcome variation associated with group membership in this comparison.</span>`);
  }
  if(!items.length)return null;
  const s=document.createElement('section');s.id='resultMeaning';s.className='card result-meaning-card';
  s.innerHTML=`<div class="head">What this means</div><div class="body"><div class="result-meaning-grid">${items.slice(0,3).map(x=>`<div class="result-meaning-item">${x}</div>`).join('')}</div><p class="result-meaning-note">Interpret these findings in the context of the decision, data quality, validation design, and any warnings shown below.</p></div>`;
  return s;
}
function insertInterpretation(r,state){
  if(document.getElementById('resultMeaning'))return;
  const node=interpretation(r,state);if(!node)return;
  const key=[...document.querySelectorAll('#journeyPendingView > .card')].find(x=>x.querySelector(':scope > .head')?.textContent.trim()==='Key evidence');
  if(key)key.insertAdjacentElement('afterend',node);else document.querySelector('.result-answer')?.insertAdjacentElement('afterend',node);
}
function renderFamilyDetails(){
  const state=root.KUAppState?.getState();if(state?.currentStep!=='results')return;ensureMetadataFreshness(state);if(document.getElementById('familyResultDetails'))return;
  const r=state.result?.payload?.result;if(!r)return;emphasizeOrdinalAnswer(r);enhanceEvidence(r);insertInterpretation(r,state);const report=document.getElementById('workflowReport')?.closest('.card'),parts=[];
  if(r.route==='regression')parts.push(regressionTargetCoding(r));
  if(r.route==='segmentation')parts.push(segmentation(r));
  if(r.route==='association'){parts.push(associations(r));parts.push(recommendations(r))}
  if(r.route==='compare_groups')parts.push(groupSummary(r));
  parts.push(warnings(r));const nodes=parts.filter(Boolean);if(!nodes.length)return;
  const wrap=document.createElement('div');wrap.id='familyResultDetails';wrap.className='result-family-details';nodes.forEach(n=>wrap.appendChild(n));
  if(report)report.insertAdjacentElement('beforebegin',wrap);else document.querySelector('.result-answer')?.insertAdjacentElement('afterend',wrap);
}
document.addEventListener('ku:render-current-analysis',renderFamilyDetails);
root.KURenderFamilyDetails=renderFamilyDetails;
})(window);
