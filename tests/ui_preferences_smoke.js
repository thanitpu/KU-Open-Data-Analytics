const assert=require('assert');
const fs=require('fs');
const path=require('path');
const {JSDOM}=require('jsdom');

const root=path.resolve(__dirname,'..');
const html='<!doctype html><html><head></head><body><header><div class="actions"><button>Load demo</button></div></header><div id="status"></div><div id="journeyPendingView"></div></body></html>';
const dom=new JSDOM(html,{url:'http://127.0.0.1:8000/app.html',runScripts:'outside-only'});
const w=dom.window;
w.eval(fs.readFileSync(path.join(root,'src/accessibility.js'),'utf8'));
w.document.dispatchEvent(new w.Event('DOMContentLoaded'));

const control=w.document.querySelector('.text-size-control');
assert.ok(control,'Text-size control should be injected into Product header');
assert.strictEqual(control.querySelectorAll('[data-ku-text-size]').length,3,'Text-size control should offer three sizes');
assert.strictEqual(w.document.documentElement.dataset.kuTextSize,'comfortable','A+ comfortable size should be the default');
assert.strictEqual(w.document.querySelector('[data-ku-text-size="comfortable"]').getAttribute('aria-pressed'),'true');

w.document.querySelector('[data-ku-text-size="large"]').click();
assert.strictEqual(w.document.documentElement.dataset.kuTextSize,'large','A++ should apply large text size');
assert.strictEqual(w.localStorage.getItem('ku-open-da-text-size'),'large','Text-size preference should persist');
assert.strictEqual(w.document.querySelector('[data-ku-text-size="large"]').getAttribute('aria-pressed'),'true');
assert.ok(w.document.querySelector('link[data-ku-ui-preferences][href="src/ui-preferences.css"]'),'UI preference stylesheet should load');

console.log('UI_PREFERENCES_SMOKE_OK (A / A+ / A++; persistence)');
