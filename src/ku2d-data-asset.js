(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.KU2DDataAsset=api;
})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const VERSION='trusted-data-asset-v1';
  const APPROVALS=new Set(['draft','approved']);
  const STORAGE_TYPES=new Set(['text','numeric','boolean','datetime','object','array','null']);
  const LINEAGE_FIELDS=Object.freeze([
    '__ku2d_data_asset_id','__ku2d_record_identity','__ku2d_acquired_at',
    '__ku2d_effective_at','__ku2d_approval_status'
  ]);
  const TOP_FIELDS=new Set(['contract_version','data_asset_id','approval_status','schema','record_count','records','provenance','acquired_at','effective_at']);
  const SCHEMA_FIELDS=new Set(['identity_field','fields']);
  const FIELD_FIELDS=new Set(['name','storage_type']);
  const PROVENANCE_FIELDS=new Set(['producer','source_ids','evidence_refs']);

  const plainObject=value=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value);
  function requireExactObject(value,allowed,label){
    if(!plainObject(value))throw new Error(`${label} must be a JSON object.`);
    const unknown=Object.keys(value).filter(key=>!allowed.has(key));
    const missing=[...allowed].filter(key=>!Object.prototype.hasOwnProperty.call(value,key));
    if(missing.length)throw new Error(`${label} is missing: ${missing.join(', ')}.`);
    if(unknown.length)throw new Error(`${label} has unknown fields: ${unknown.join(', ')}.`);
  }
  function nonEmptyString(value,label){
    if(typeof value!=='string'||!value.trim())throw new Error(`${label} must be a non-empty string.`);
    return value.trim();
  }
  function timestamp(value,label){
    const raw=nonEmptyString(value,label);
    if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(raw)||!Number.isFinite(Date.parse(raw))){
      throw new Error(`${label} must be an ISO 8601 date-time with an explicit timezone.`);
    }
    return raw;
  }
  function stringList(value,label){
    if(!Array.isArray(value)||!value.length)throw new Error(`${label} must contain at least one value.`);
    return value.map((item,index)=>nonEmptyString(item,`${label}[${index}]`));
  }
  function valueMatchesStorage(value,storageType){
    if(value===null)return true;
    if(storageType==='text')return typeof value==='string';
    if(storageType==='numeric')return typeof value==='number'&&Number.isFinite(value);
    if(storageType==='boolean')return typeof value==='boolean';
    if(storageType==='datetime')return typeof value==='string'&&Number.isFinite(Date.parse(value));
    if(storageType==='object')return plainObject(value);
    if(storageType==='array')return Array.isArray(value);
    return storageType==='null'&&value===null;
  }
  function validateAsset(asset){
    requireExactObject(asset,TOP_FIELDS,'Trusted data asset');
    if(asset.contract_version!==VERSION)throw new Error(`Unsupported contract_version: ${asset.contract_version}.`);
    const dataAssetId=nonEmptyString(asset.data_asset_id,'data_asset_id');
    if(!APPROVALS.has(asset.approval_status))throw new Error('approval_status must be draft or approved.');
    requireExactObject(asset.schema,SCHEMA_FIELDS,'schema');
    const identityField=nonEmptyString(asset.schema.identity_field,'schema.identity_field');
    if(!Array.isArray(asset.schema.fields)||!asset.schema.fields.length)throw new Error('schema.fields must contain at least one field.');
    const names=new Set();
    const fields=asset.schema.fields.map((field,index)=>{
      requireExactObject(field,FIELD_FIELDS,`schema.fields[${index}]`);
      const name=nonEmptyString(field.name,`schema.fields[${index}].name`);
      if(names.has(name))throw new Error(`Duplicate schema field: ${name}.`);
      if(LINEAGE_FIELDS.includes(name))throw new Error(`Schema field ${name} is reserved for KU2D lineage.`);
      if(!STORAGE_TYPES.has(field.storage_type))throw new Error(`Unsupported storage_type for ${name}.`);
      names.add(name);
      return {name,storage_type:field.storage_type};
    });
    if(!names.has(identityField))throw new Error('schema.identity_field must name a declared field.');
    if(!Number.isInteger(asset.record_count)||asset.record_count<1)throw new Error('record_count must be a positive integer.');
    if(!Array.isArray(asset.records))throw new Error('records must be an array.');
    if(asset.records.length!==asset.record_count)throw new Error(`record_count ${asset.record_count} does not match ${asset.records.length} records.`);
    const identities=new Set();
    const records=asset.records.map((record,index)=>{
      if(!plainObject(record))throw new Error(`records[${index}] must be an object.`);
      const unknown=Object.keys(record).filter(name=>!names.has(name));
      const missing=fields.map(field=>field.name).filter(name=>!Object.prototype.hasOwnProperty.call(record,name));
      if(missing.length)throw new Error(`records[${index}] is missing: ${missing.join(', ')}.`);
      if(unknown.length)throw new Error(`records[${index}] has unknown fields: ${unknown.join(', ')}.`);
      for(const field of fields)if(!valueMatchesStorage(record[field.name],field.storage_type))throw new Error(`records[${index}].${field.name} does not match storage_type ${field.storage_type}.`);
      const identity=nonEmptyString(String(record[identityField]??''),`records[${index}].${identityField}`);
      if(identities.has(identity))throw new Error(`Duplicate identity ${identity} in ${dataAssetId}.`);
      identities.add(identity);
      return {...record};
    });
    requireExactObject(asset.provenance,PROVENANCE_FIELDS,'provenance');
    if(asset.provenance.producer!=='KU2D')throw new Error('provenance.producer must be KU2D.');
    const provenance={
      producer:'KU2D',
      source_ids:stringList(asset.provenance.source_ids,'provenance.source_ids'),
      evidence_refs:stringList(asset.provenance.evidence_refs,'provenance.evidence_refs')
    };
    return {
      contract_version:VERSION,data_asset_id:dataAssetId,approval_status:asset.approval_status,
      schema:{identity_field:identityField,fields},record_count:asset.record_count,records,provenance,
      acquired_at:timestamp(asset.acquired_at,'acquired_at'),effective_at:timestamp(asset.effective_at,'effective_at')
    };
  }
  function schemaFingerprint(asset){
    return `${asset.schema.identity_field}|${asset.schema.fields.map(field=>`${field.name}:${field.storage_type}`).join('|')}`;
  }
  function validateAssets(input){
    const list=Array.isArray(input)?input:[input];
    if(!list.length)throw new Error('Select at least one KU2D data asset.');
    const assets=list.map(validateAsset);
    const assetIds=new Set();
    for(const asset of assets){
      if(assetIds.has(asset.data_asset_id))throw new Error(`Duplicate data_asset_id: ${asset.data_asset_id}.`);
      assetIds.add(asset.data_asset_id);
    }
    const expected=schemaFingerprint(assets[0]);
    const incompatible=assets.find(asset=>schemaFingerprint(asset)!==expected);
    if(incompatible)throw new Error(`Schema for ${incompatible.data_asset_id} is incompatible with ${assets[0].data_asset_id}.`);
    const rows=[];
    for(const asset of assets){
      const identityField=asset.schema.identity_field;
      asset.records.forEach(record=>rows.push({
        ...record,
        __ku2d_data_asset_id:asset.data_asset_id,
        __ku2d_record_identity:String(record[identityField]),
        __ku2d_acquired_at:asset.acquired_at,
        __ku2d_effective_at:asset.effective_at,
        __ku2d_approval_status:asset.approval_status
      }));
    }
    return {
      version:VERSION,
      assets,
      rows,
      dataColumns:assets[0].schema.fields.map(field=>field.name),
      lineageColumns:[...LINEAGE_FIELDS],
      allColumns:[...assets[0].schema.fields.map(field=>field.name),...LINEAGE_FIELDS],
      approval:{
        productionApproved:assets.every(asset=>asset.approval_status==='approved'),
        statuses:Object.fromEntries(assets.map(asset=>[asset.data_asset_id,asset.approval_status]))
      },
      acquiredAt:assets.map(asset=>asset.acquired_at),
      effectiveAt:assets.map(asset=>asset.effective_at)
    };
  }
  function parseJSON(text,label='KU2D asset'){
    let value;
    try{value=JSON.parse(String(text??''));}catch(error){throw new Error(`${label} is not valid JSON: ${error.message}`);}
    return value;
  }
  return Object.freeze({VERSION,LINEAGE_FIELDS,parseJSON,validateAsset,validateAssets,schemaFingerprint,valueMatchesStorage});
});
