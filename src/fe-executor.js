// KU Open DA — trusted browser Feature Engineering Executor + lineage.
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.KUFeatureEngineeringExecutor=api;
})(typeof window!=='undefined'?window:globalThis,function(){
'use strict';
const VERSION='1.0';
const ALLOWED_OPERATIONS=new Set(['reference_year_minus','date_difference','extract_month','extract_day_of_week','log1p','row_sum','group_rare_categories']);
const missing=v=>v===''||v===null||v===undefined||(typeof v==='number'&&Number.isNaN(v));
const finite=v=>{if(missing(v))return null;const n=Number(v);return Number.isFinite(n)?n:null};
const unique=a=>[...new Set((Array.isArray(a)?a:[]).filter(Boolean))];
function cleanName(value){return String(value||'Derived_Feature').trim().replace(/\s+/g,'_')||'Derived_Feature'}
function resolvedOutputName(desired,used){let base=cleanName(desired),name=base,i=2;while(used.has(name)){name=`${base}_FE${i===2?'':`_${i}`}`;i++}used.add(name);return name}
function selectedRecommendations(plan={}){
  const fe=plan.preparation?.featureEngineering||{};
  if(!fe.reviewed||fe.status==='skipped')return[];
  const ids=new Set(unique(fe.selectedIds||[]));
  return (Array.isArray(fe.recommendations)?fe.recommendations:[]).filter(x=>ids.has(x.id));
}
function compilePlan({plan={},baseColumns=[]}={}){
  const used=new Set(baseColumns||[]),lineage=[];
  for(const rec of selectedRecommendations(plan)){
    if(!ALLOWED_OPERATIONS.has(rec.operation))throw new Error(`Unsupported browser FE operation: ${rec.operation}`);
    const sources=unique(rec.source_fields||[]);
    if(!sources.length)throw new Error(`Feature recommendation ${rec.id||''} has no source field.`);
    const output=resolvedOutputName(rec.output_field||`${sources[0]}_${rec.operation}`,used);
    lineage.push({
      id:rec.id||null,
      output_field:output,
      requested_output_field:rec.output_field||null,
      source_fields:sources,
      operation:rec.operation,
      parameters:{...(rec.parameters||{})},
      reason:rec.reason||null,
      basis:[...(rec.basis||[])],
      confidence:Number.isFinite(Number(rec.confidence))?Number(rec.confidence):null,
      recommended_by:'KU Analytical Intelligence',
      executed_by:'browser',
      executor_version:VERSION,
      status:'ready'
    });
  }
  return{schema_version:'1.0',executor_version:VERSION,lineage,derived_fields:lineage.map(x=>x.output_field)};
}
function dateMs(v){if(missing(v))return null;const t=Date.parse(v);return Number.isFinite(t)?t:null}
function buildRareSet(rows,field,thresholdPct){const counts=new Map();let n=0;for(const row of rows){const v=row?.[field];if(missing(v))continue;n++;const k=String(v);counts.set(k,(counts.get(k)||0)+1)}const limit=Number.isFinite(Number(thresholdPct))?Number(thresholdPct):1;return new Set([...counts].filter(([,c])=>n&&100*c/n<=limit).map(([k])=>k))}
function contextFor(lineage,rows){const ctx={rareSets:new Map()};for(const item of lineage){if(item.operation==='group_rare_categories'){const field=item.source_fields[0];ctx.rareSets.set(item.output_field,buildRareSet(rows,field,item.parameters?.rare_threshold_pct))}}return ctx}
function executeOne(item,row,ctx){
  const p=item.parameters||{},src=item.source_fields||[];
  if(item.operation==='reference_year_minus'){
    const v=finite(row?.[src[0]]),ref=finite(p.reference_year);return v===null||ref===null?'':ref-v;
  }
  if(item.operation==='date_difference'){
    const a=dateMs(row?.[src[0]]),b=dateMs(p.reference_date);if(a===null||b===null)return'';const days=(b-a)/86400000;return p.direction==='source_minus_reference'?-days:days;
  }
  if(item.operation==='extract_month'){
    const t=dateMs(row?.[src[0]]);return t===null?'':new Date(t).getUTCMonth()+1;
  }
  if(item.operation==='extract_day_of_week'){
    const t=dateMs(row?.[src[0]]);if(t===null)return'';const day=new Date(t).getUTCDay();return day===0?7:day;
  }
  if(item.operation==='log1p'){
    const v=finite(row?.[src[0]]);return v===null||v<0?'':Math.log1p(v);
  }
  if(item.operation==='row_sum'){
    const vals=src.map(name=>finite(row?.[name]));return vals.some(v=>v===null)?'':vals.reduce((s,v)=>s+v,0);
  }
  if(item.operation==='group_rare_categories'){
    const v=row?.[src[0]];if(missing(v))return'';return ctx.rareSets.get(item.output_field)?.has(String(v))?(p.replacement||'Other'):v;
  }
  throw new Error(`Unsupported browser FE operation: ${item.operation}`);
}
function buildAnalyticalDataset({rows=[],plan={},baseColumns=[]}={}){
  const base=unique(baseColumns),compiled=compilePlan({plan,baseColumns:base}),ctx=contextFor(compiled.lineage,rows);
  const columns=[...base,...compiled.derived_fields];
  const outputRows=rows.map(row=>{
    const out={};for(const c of base)out[c]=row?.[c]??'';
    for(const item of compiled.lineage)out[item.output_field]=executeOne(item,row,ctx);
    return out;
  });
  return{columns,rows:outputRows,lineage:compiled.lineage,manifest:{schema_version:'1.0',executor_version:VERSION,applied:compiled.lineage.length>0,derived_fields:compiled.derived_fields,lineage:compiled.lineage}};
}
function outputFields(plan={},baseColumns=[]){return compilePlan({plan,baseColumns}).derived_fields}
return Object.freeze({VERSION,ALLOWED_OPERATIONS:[...ALLOWED_OPERATIONS],selectedRecommendations,compilePlan,buildAnalyticalDataset,outputFields});
});
