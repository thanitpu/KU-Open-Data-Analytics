const assert=require('assert');
const fs=require('fs');
const path=require('path');

const root=path.resolve(__dirname,'..');
const srcDir=path.join(root,'src');
const appEntry=process.env.KU_APP_ENTRY||'app.html';
const appPath=path.join(root,appEntry);
const publicPath=path.join(root,'index.html');

assert.strictEqual(appEntry,'app.html','functional CI must treat app.html as the canonical Product entry');
assert.ok(fs.existsSync(appPath),'canonical Product app.html must exist');
assert.ok(fs.existsSync(publicPath),'Public Landing index.html must exist');

const appShell=fs.readFileSync(appPath,'utf8');
const publicShell=fs.readFileSync(publicPath,'utf8');
assert.notStrictEqual(publicShell,appShell,'Public index.html and Product app.html must be separate entry documents');
assert.ok(!/(?:src|href)=["']\//i.test(appShell),'app.html assets must use relative paths rather than root-absolute /... paths');
assert.ok(!/(?:src|href)=["']\/(?!\/)/i.test(publicShell),'index.html authored local assets must use relative paths rather than root-absolute /... paths');

for(const required of ['src/landing.css','src/landing-copy.js','src/landing-content.js','src/landing.js','href="app.html"']){
  assert.ok(publicShell.includes(required),`Public Landing missing contract: ${required}`);
}
for(const protectedAsset of ['src/app.css','src/app.js','src/state.js','src/journey.js','src/ai-analytics.js']){
  assert.ok(!publicShell.includes(protectedAsset),`Public Landing must not import Product asset: ${protectedAsset}`);
}
for(const landingAsset of ['src/landing.css','src/landing.js','src/landing-copy.js','src/landing-content.js']){
  assert.ok(!appShell.includes(landingAsset),`Product app.html must not import Landing asset: ${landingAsset}`);
}
for(const productAsset of ['src/app.css','src/state.js','src/app.js','src/ai-analytics.js','src/journey.js']){
  assert.ok(appShell.includes(productAsset),`Product app.html missing required asset: ${productAsset}`);
}

const productRuntimeFiles=fs.readdirSync(srcDir).filter(name=>name.endsWith('.js')&&!name.startsWith('landing'));
for(const file of productRuntimeFiles){
  const text=fs.readFileSync(path.join(srcDir,file),'utf8');
  assert.ok(!text.includes('index.html'),`${file}: runtime Product code must not hard-code Public Home filename`);
  assert.ok(!/location\.(?:href|assign|replace)\s*(?:=|\()\s*["']\//.test(text),`${file}: runtime Product navigation must not hard-code the site root`);
}

console.log('FRONTEND_ENTRY_GUARD_OK (index.html=Public Landing; app.html=Product)');
