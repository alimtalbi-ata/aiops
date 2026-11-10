#!/usr/bin/env python3
"""Exercise actual FS1097 JS loading announcements, errors, and stale requests."""
import pathlib
import re
import shutil
import subprocess
import sys

source = pathlib.Path(__file__).resolve().parents[1] / "fs1097_patch.py"
match = re.search(r'js_add = r"""(.*?)"""', source.read_text(), re.S)
assert match, "inline history JavaScript not found"
if not shutil.which("node"):
    sys.exit("NOT_EXECUTED: Node.js unavailable")
js = re.sub(r'\nloadHistory\(\);\s*$', '\n', match.group(1))
harness = r"""
const assert = require('node:assert/strict');
const elements = {};
function el(id) {
 if(!elements[id]) elements[id] = {
   value: id==='history-metric'?'availability':'1h',
   disabled:false, textContent:'', children:[], attrs:{},
   setAttribute(k,v){this.attrs[k]=v},
   replaceChildren(...v){this.children=v},
   append(...v){this.children.push(...v)},
   addEventListener(){}
 };
 return elements[id];
}
global.$=el;
global.document={
 createElementNS:tag=>({tag,setAttribute(){},textContent:''}),
 createElement:tag=>({tag,children:[],append(...v){this.children.push(...v)},textContent:''})
};
let pending, mode='pending';
global.fetch=()=>{
 if(mode==='pending') return new Promise(resolve=>{pending=resolve});
 if(mode==='deny') return Promise.resolve({ok:false,status:403});
 return Promise.resolve({ok:true,status:200,json:async()=>({
 metric:'availability',window:'1h',step_seconds:60,
 series:[{job:'j',instance:'i',points:[[1,0],[2,1]]}]
 })});
};
"""
tail = r"""
(async()=>{
 const first=loadHistory();
 assert.equal(el('history-chart').attrs['aria-busy'],'true');
 assert.equal(el('history-refresh').disabled,true);
 mode='deny';
 await loadHistory();
 assert.equal(el('history-chart').attrs['aria-busy'],'false');
 assert.equal(el('history-refresh').disabled,false);
 assert.match(el('history-status').textContent,/Accès refusé/);
 assert.equal(el('history-legend').children.length,0);
 pending({ok:true,status:200,json:async()=>({})});
 await first;
 assert.equal(el('history-chart').attrs['aria-busy'],'false');
 assert.match(el('history-status').textContent,/Accès refusé/);
 mode='allow';
 await loadHistory();
 assert.equal(el('history-chart').attrs['aria-busy'],'false');
 assert.equal(el('history-legend').children.length,1);
 console.log('PASS: busy, denied, stale response and recovery');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
result = subprocess.run(["node", "-e", harness+js+tail], capture_output=True, text=True, timeout=15)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
sys.exit(result.returncode)
