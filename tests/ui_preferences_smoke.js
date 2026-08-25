const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {JSDOM}=require('jsdom');

const root=path.resolve(__dirname,'..');
const appHtml=fs.readFileSync(path.join(root,'app.html'),'utf8');
const dom=new JSDOM(appHtml,{url:'http://127.0.0.1:8000/app.html',runScripts:'outside-only'});
const w=dom.window;

// Exercise the real Product header and the real preference module.
w.eval(fs.readFileSync(path.join(root,'src/accessibility.js'),'utf8'));
w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
const control=w.document.querySelector('.text-size-control');
assert.ok(control,'Real app.html header should receive the text-size control');
assert.ok(w.document.querySelector('header .actions .text-size-control'),'Text-size control must live in the Product top header');
assert.strictEqual(control.querySelectorAll('[data-ku-text-size]').length,3,'Text-size control should offer A / A+ / A++');
assert.strictEqual(w.document.documentElement.dataset.kuTextSize,'comfortable','A+ comfortable size should be the default');
assert.strictEqual(w.document.querySelector('[data-ku-text-size="comfortable"]').getAttribute('aria-pressed'),'true');
assert.ok(w.document.querySelector('link[data-ku-ui-preferences][href="src/ui-preferences.css"]'),'UI preference stylesheet should load');

w.document.querySelector('[data-ku-text-size="large"]').click();
assert.strictEqual(w.document.documentElement.dataset.kuTextSize,'large','A++ should apply large text size');
assert.strictEqual(w.localStorage.getItem('ku-open-da-text-size'),'large','Text-size preference should persist');

// Local Manual UAT must resolve to the branch-matched FastAPI, never Render.
w.eval(fs.readFileSync(path.join(root,'src/ai-analytics.js'),'utf8'));
assert.strictEqual(w.eval('KU_ANALYTICS_API_BASE'),'http://127.0.0.1:8001','localhost Product must resolve analytics API to local port 8001');

console.log('UI_PREFERENCES_SMOKE_OK (real app header + A/A+/A++; local API 8001)');
