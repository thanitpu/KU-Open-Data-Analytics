const assert=require('assert');
const fs=require('fs');
const path=require('path');

const root=path.resolve(__dirname,'..');
const srcDir=path.join(root,'src');
const appEntry=process.env.KU_APP_ENTRY||'index.html';
const appPath=path.join(root,appEntry);

assert.ok(fs.existsSync(appPath),`configured analytics app entry does not exist: ${appEntry}`);

const shell=fs.readFileSync(appPath,'utf8');
assert.ok(!/(?:src|href)=["']\//i.test(shell),`${appEntry}: app assets must use relative paths rather than root-absolute /... paths`);

for(const file of fs.readdirSync(srcDir).filter(name=>name.endsWith('.js'))){
  const text=fs.readFileSync(path.join(srcDir,file),'utf8');
  assert.ok(!text.includes('index.html'),`${file}: runtime product code must not hard-code index.html; analytics app will migrate to app.html`);
  assert.ok(!/location\.(?:href|assign|replace)\s*(?:=|\()\s*["']\//.test(text),`${file}: runtime navigation must not hard-code the site root`);
}

console.log(`FRONTEND_ENTRY_GUARD_OK (${appEntry})`);
