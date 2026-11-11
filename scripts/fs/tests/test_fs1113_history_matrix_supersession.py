#!/usr/bin/env python3
"""Candidate-only FS1113 race/auth/period regression using actual inline JS.

Synthetic Node DOM: NOT a Chromium, CSP, Debian or live E2E qualification.
"""
import pathlib
import re
import shutil
import subprocess
import sys

source = pathlib.Path(__file__).resolve().parents[1] / "fs1097_patch.py"
match = re.search(r'js_add = r"""(.*?)"""', source.read_text(encoding="utf-8"), re.S)
assert match, "History JS not found"
if not shutil.which("node"):
    sys.exit("NOT_EXECUTED: Node.js required")
js = re.sub(r'\nloadHistory\(\);\s*$', '\n', match.group(1))
harness = r"""
const assert = require('node:assert/strict');
const elements = {};
function el(id) {
 if (!elements[id]) elements[id] = {
  value: id==='history-metric'?'availability':'1h', disabled:false,
  textContent:'', children:[], attrs:{},
  setAttribute(k,v){this.attrs[k]=v},
  replaceChildren(...v){this.children=v}, append(...v){this.children.push(...v)},
  addEventListener(){}
 };
 return elements[id];
}
global.$=el;
global.document={
 createElementNS:tag=>({tag,attrs:{},setAttribute(k,v){this.attrs[k]=v},textContent:''}),
 createElement:tag=>({tag,children:[],append(...v){this.children.push(...v)},textContent:''})
};
const pending=[];
global.fetch=(url,options)=>new Promise((resolve,reject)=>{
 assert.equal(options.credentials,'same-origin');
 assert.equal(options.headers.Accept,'application/json');
 const u=new URL(url,'https://portal.invalid');
 assert.equal(u.origin,'https://portal.invalid');
 pending.push({url:u,options,resolve,reject});
});
function respond(request,status,metric,windowSize){
 request.resolve({ok:status===200,status,json:async()=>({
  metric,window:windowSize,step_seconds:60,
  series:[{job:'j',instance:'i',points:[[100,1],[160,0]]}]
 })});
}
"""
tail = r"""
(async()=>{
 for(const metric of ['availability','scrape_duration']){
  for(const windowSize of ['1h','6h','24h']){
   el('history-metric').value=metric;el('history-window').value=windowSize;
   const p=loadHistory();const req=pending.at(-1);
   assert.equal(req.url.searchParams.get('metric'),metric);
   assert.equal(req.url.searchParams.get('window'),windowSize);
   assert.equal(el('history-chart').attrs['aria-busy'],'true');
   respond(req,200,metric,windowSize);await p;
   assert.equal(el('history-legend').children.length,1);
   assert.equal(el('history-chart').attrs['aria-busy'],'false');
   assert.match(el('history-chart').attrs['aria-label'],/1 séries/);
  }
 }
 // An older 403 must never overwrite a newer authorized response.
 el('history-metric').value='availability';el('history-window').value='1h';
 const stale=loadHistory(), old=pending.at(-1);
 el('history-window').value='6h';
 const current=loadHistory(), fresh=pending.at(-1);
 assert.equal(old.options.signal.aborted,true);
 respond(fresh,200,'availability','6h');await current;
 respond(old,403,'availability','1h');await stale;
 assert.equal(el('history-legend').children.length,1);
 assert.match(el('history-chart').attrs['aria-label'],/6h · 1 séries/);
 assert.equal(el('history-chart').attrs['aria-busy'],'false');
 // Current 403 clears the chart, then an authorized retry recovers.
 const denied=loadHistory(), forbidden=pending.at(-1);
 respond(forbidden,403,'availability','6h');await denied;
 assert.equal(el('history-legend').children.length,0);
 assert.match(el('history-status').textContent,/Accès refusé/);
 const retry=loadHistory(), allowed=pending.at(-1);
 respond(allowed,200,'availability','6h');await retry;
 assert.equal(el('history-legend').children.length,1);
 assert.equal(el('history-refresh').disabled,false);
 console.log('PASS: 6 metric/window combinations, superseded 403, current 403, recovery');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
result = subprocess.run(["node", "-e", harness + js + tail], capture_output=True, text=True, timeout=30)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
sys.exit(result.returncode)
