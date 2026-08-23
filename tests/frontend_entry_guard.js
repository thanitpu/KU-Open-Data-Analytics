const assert=require('assert');
const fs=require('fs');
const path=require('path');

const root=path.resolve(__dirname,'..');
const srcDir=path.join(root,'src');
const appEntry=process.env.KU_APP_ENTRY||'app.html';
const appPath=path.join(root,appEntry);

assert.strictEqual(appEntry,'app.html','functional CI must treat app.html as the canonical Product entry');
assert.ok(fs.existsSync(appPath),`configured analytics app entry does not exist: ${appEntry}`);

const shell=fs.readFileSync(appPath,'utf8');
assert.ok(!/(?:src|href)=["']\//i.test(shell),`${appEntry}: app assets must use relative paths rather than root-absolute /... paths`);

const compatibilityIndex=path.join(root,'index.html');
assert.ok(fs.existsSync(compatibilityIndex),'temporary compatibility index.html must remain until final Landing promotion');
assert.strictEqual(fs.readFileSync(compatibilityIndex,'utf8'),shell,'during the transition index.html must remain an exact compatibility mirror of app.html; remove this mirror assertion only in the explicit Landing promotion step');

for(const file of fs.readdirSync(srcDir).filter(name=>name.endsWith('.js'))){
  const text=fs.readFileSync(path.join(srcDir,file),'utf8');
  assert.ok(!text.includes('index.html'),`${file}: runtime Product code must not hard-code index.html; public home will own that filename`);
  assert.ok(!/location\.(?:href|assign|replace)\s*(?:=|\()\s*["']\//.test(text),`${file}: runtime navigation must not hard-code the site root`);
}

console.log(`FRONTEND_ENTRY_GUARD_OK (${appEntry}; index compatibility mirror verified)`);
