const assert=require('assert');
const manifest=require('../src/profile-manifest.js');
const insights=require('../src/profile-insights.js');

const headers=['Date','Sales','Income','Segment'];
const data=[
  {Date:'2026-01-01',Sales:10,Income:20,Segment:'A'},
  {Date:'2026-01-02',Sales:11,Income:22,Segment:'A'},
  {Date:'2026-01-03',Sales:12,Income:24,Segment:'B'},
  {Date:'2026-01-04',Sales:13,Income:26,Segment:'B'},
  {Date:'2026-01-05',Sales:14,Income:28,Segment:'A'},
  {Date:'2026-01-06',Sales:15,Income:30,Segment:'A'},
  {Date:'2026-01-07',Sales:16,Income:32,Segment:'B'},
  {Date:'2026-01-08',Sales:17,Income:34,Segment:'A'},
  {Date:'2026-01-09',Sales:18,Income:36,Segment:'B'},
  {Date:'2026-01-10',Sales:500,Income:1000,Segment:'A'},
];
const out=manifest.build({headers,data,types:{Date:'text',Sales:'numeric',Income:'numeric',Segment:'text'},meta:{Date:{level:'Nominal'},Sales:{level:'Scale'},Income:{level:'Scale'},Segment:{level:'Nominal'}}});
const vm=insights.buildViewModel(out);
assert.equal(vm.numeric.length,2);
assert.equal(vm.categorical.length,1);
assert.equal(vm.temporal.length,1);
assert(vm.shapeCounts.skewed>=1);
assert(vm.outlierSignals.length>=1);
assert.equal(vm.temporal[0].temporal.granularity,'daily');
assert.equal(vm.categorical[0].frequency.top[0].value,'A');
console.log('[Profile Insights smoke completed]');
