const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('scripts/fs/fs1097_patch.py', 'utf8');
const match = source.match(/const seenTargets=new Set\(\);([\s\S]*?)const points=series\.flatMap/);
assert.ok(match, 'history series filtering source not found');
const filter = new Function('data', 'historyValidPoint', `const seenTargets=new Set();${match[1]}return series;`);
const valid = p => Array.isArray(p)&&p.length===2&&p.every(v=>(typeof v==='number'||typeof v==='string')&&String(v).trim()!==''&&Number.isFinite(Number(v)));
const data={series:[
 {job:'invalid',instance:'a',points:[[1,null],[2,' '],[3,'NaN']]},
 {job:'good',instance:'b',points:[[1,0],[2,'1']]},
 {job:'good',instance:'b',points:[[3,4]]},
 {job:'invalid',instance:'a',points:[[4,5]]},
 {points:[[5,7]]}
]};
const result=filter(data,valid);
assert.equal(result.length,3);
assert.deepEqual(result.map(s=>s.job||'unknown'),['good','invalid','unknown']);
assert.equal(result[0].points[0][1],0);
console.log('FS1113_INVALID_SERIES_FILTER=PASS');
