const assert=require('assert');
const fs=require('fs');
const path=require('path');

const root=path.resolve(__dirname,'..');
const read=relativePath=>fs.readFileSync(path.join(root,relativePath),'utf8');

const canonicalRepository='thanitpu/KU2A-Analytics';
const retiredRepository='thanitpu/KU-Open-Data-Analytics';

const render=read('render.yaml');
assert.ok(
  render.includes(`repo: https://github.com/${canonicalRepository}`),
  'Render Blueprint must follow the canonical KU2A repository',
);
assert.ok(
  !render.includes(retiredRepository),
  'Render Blueprint must not depend on the retired repository name',
);

const preview=read('preview.html');
assert.ok(
  preview.includes(`https://raw.githack.com/${canonicalRepository}/`),
  'commit preview must resolve assets from the canonical KU2A repository',
);
assert.ok(
  !preview.includes(retiredRepository),
  'commit preview must not depend on the retired repository name',
);

const prPreview=read('.github/workflows/pr-browser-preview.yml');
assert.ok(
  prPreview.includes('const repo = pr.head.repo.full_name;'),
  'PR previews must derive repository identity from the event payload',
);
assert.ok(
  !prPreview.includes(retiredRepository),
  'PR preview workflow must not hard-code the retired repository name',
);

const analyticsClient=read('src/ai-analytics.js');
assert.ok(
  analyticsClient.includes('https://ku-open-data-analytics-api.onrender.com'),
  'the compatible production API endpoint must remain unchanged by the repository rename',
);

console.log('REPOSITORY_IDENTITY_SMOKE_OK (repo=KU2A-Analytics; product/API compatibility preserved)');
