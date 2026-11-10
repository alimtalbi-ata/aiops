#!/usr/bin/env python3
"""Exercise the actual FS1097 inline JS with a minimal DOM and mocked same-origin API."""
import pathlib
import re
import shutil
import subprocess
import sys

source = pathlib.Path(__file__).resolve().parents[1] / "fs1097_patch.py"
match = re.search(r'js_add = r"""(.*?)"""', source.read_text(), re.S)
assert match, "FS1097 inline JS missing"
if not shutil.which("node"):
    print("NOT_EXECUTED: node unavailable")
    sys.exit(2)

harness = r"""
const assert=require('node:assert/strict');
const elements={};
function element(id){
 if(!elements[id]) elements[id]={
  value:id==='history-metric'?'availability':'1h',
  textContent:'',disabled:false,children:[],
  replaceChildren(...xs){this.children=xs},
  append(...xs){this.children.push(...xs)},
  addEventListener(){},setAttribute(){},
 };
 return elements[id];
}
global.$=element;
global.document={
 createElementNS:tag=>({tag,textContent:'',setAttribute(){}}),
 createElement:tag=>({tag,textContent:'',className:'',children:[],append(...xs){this.children.push(...xs)}})
};
global.fetch=async(url,opts)=>{
 assert.equal(opts.credentials,'same-origin');
 assert.equal(opts.headers.Accept,'application/json');
 if(mode==='deny') return {ok:false,status:403};
 return {ok:true,status:200,json:async()=>({metric:'availability',window:'1h',step_seconds:60,
 series:[{job:'j',instance:'i',points:[[1,0],[2,1]]}]})};
};
let mode='deny';
"""
const tail = r"""
(async()=>{
 await loadHistory();
 assert.match(element('history-status').textContent,/Accès refusé/);
 assert.equal(element('history-legend').children.length,0);
 assert.equal(element('history-refresh').disabled,false);
 mode='allow';
 await loadHistory();
 assert.equal(element('history-legend').children.length,1);
 assert.match(element('history-status').textContent,/1 séries/);
 console.log('PASS: 403 fail closed, no legend; retry restores one series');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
# The inline JS calls loadHistory on initialization; the first call is denied.
# Re-run explicitly to assert the completed denied state.
js = match.group(1).replace('loadHistory();\n', '', 1) if False else match.group(1)
js = re.sub(r'\nloadHistory\(\);\s*$', '\n', js)
result = subprocess.run(["node", "-e", harness + js + tail], text=True, capture_output=True)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
sys.exit(result.returncode)
