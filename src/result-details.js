// KU Open DA — family-specific Step 6 details from validated payloads.
(function(root){
'use strict';
const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
function card(title,body,cls=''){const s=document.createElement('section');s.className=`card result-family-detail ${cls}`.trim();s.innerHTML=`<div class="head">${safe(title)}</div><div class="body">${body}</div>`;return s}
function table(headers,rows){return `<div class="table"><table><thead><tr>${headers.map(h=>`<th>${safe(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(v=>`<td>${safe(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`}
function regressionTargetCoding(r){const enc=r.method?.target_encoding;if(enc?.type!=='ordinal_rank'||!enc.mapping)return null;const rows=Object.entries(enc.mapping).map(([label,rank])=>[label,rank]);return card('Target Coding',`<p class="result-coding-note">The ordinal target was encoded as ordered ranks for modeling. Rank order is meaningful; equal spacing between adjacent categories is not established by the coding.</p>${table(['Category','Rank'],rows)}`)}
function emphasizeOrdinalAnswer(r){if(r.route!=='regression'||r.method?.target_encoding?.type!=='ordinal_rank')return;const answer=document.querySelector('.result-answer h2');if(answer&&!answer.textContent.startsWith('Ordinal rank-coded target · '))answer.textContent=`Ordinal rank-coded target · ${answer.textContent}`}
function segmentation(r){const f=r.findings;if(!f||Array.isArray(f)||typeof f!=='object')return null;const rows=Object.entries(f).map(([segment,x])=>[segment,`${num(x?.size_pct,1)}%`,(x?.high||[]).join(', ')||'—',(x?.low||[]).join(', ')||'—']);return rows.length?card('Segment Profiles',table(['Segment','Size','Higher than overall','Lower than overall'],rows)) : null}
function associations(r){const f=Array.isArray(r.findings)?r.findings:[];if(!f.length)return null;const rows=f.slice(0,12).map(x=>[x.relationship||x.title||'Relationship',num(x.effect,3),Number.isFinite(Number(x.q_value))?num(x.q_value,4):'—',x.interpretation||x.subtitle||'']);return card('Top Supported Associations',table(['Relationship','Effect','q-value','Interpretation'],rows))}
function groupSummary(r){const f=Array.isArray(r.group_summaries)?r.group_summaries:[];if(!f.length)return null;const rows=f.map(x=>[x.group,x.n,num(x.mean),x.sd===null?'—':num(x.sd)]);return card('Group Summary',table(['Group','N','Mean','SD'],rows))}
function warnings(r){const w=Array.isArray(r.warnings)?r.warnings.filter(Boolean):[];if(!w.length)return null;return card('Warnings / Guardrails',w.map(x=>`<p class="result-warning-item">⚠ ${safe(x)}</p>`).join(''),'result-warning-card')}
function recommendations(r){const list=Array.isArray(r.recommendations)?r.recommendations:[];if(!list.length)return null;return card('Recommended Follow-up',list.map(x=>`<div class="result-recommendation"><b>${safe(x.analysis||'Follow-up')}</b><span>${safe(x.reason||'')}</span></div>`).join(''))}
function renderFamilyDetails(){
  const state=root.KUAppState?.getState();if(state?.currentStep!=='results'||document.getElementById('familyResultDetails'))return;
  const r=state.result?.payload?.result;if(!r)return;emphasizeOrdinalAnswer(r);const report=document.getElementById('workflowReport')?.closest('.card'),parts=[];
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
