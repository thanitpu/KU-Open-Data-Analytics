(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.KUCSVExporter=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const quote=value=>/[",\n\r]/.test(String(value??''))?`"${String(value??'').replace(/"/g,'""')}"`:String(value??'');
  function toCSV(rows){if(!Array.isArray(rows)||!rows.length)return '';const headers=[...new Set(rows.flatMap(row=>Object.keys(row||{})))];return [headers.map(quote).join(','),...rows.map(row=>headers.map(header=>quote(row?.[header])).join(','))].join('\n');}
  function download(filename,text,mime='text/csv;charset=utf-8'){const blob=new Blob(['\uFEFF',text],{type:mime}),url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=filename;document.body.appendChild(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return {toCSV,download};
});
