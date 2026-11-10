#!/usr/bin/env python3
"""Regression: Prometheus missing scrape intervals must not be drawn as continuity."""
import pathlib
import re
import subprocess
import sys

source = pathlib.Path(__file__).with_name("fs1097_patch.py").read_text(encoding="utf-8")
match = re.search(r"function historySegmentedPath\(samples,x,y,stepSeconds\)\{[^\n]+\}", source)
assert match, "historySegmentedPath with stepSeconds not found"
js = """
function historyValidPoint(p){return Array.isArray(p)&&p.length===2&&p.every(v=>(typeof v==="number"||typeof v==="string")&&String(v).trim()!==""&&Number.isFinite(Number(v)))}
""" + match.group(0) + """
const x=v=>Number(v),y=v=>Number(v);
const cases=[
 [[[0,1],[60,2],[120,3]],60,"M0.00 1.00 L60.00 2.00 L120.00 3.00"],
 [[[0,1],[180,2]],60,"M0.00 1.00 M180.00 2.00"],
 [[[0,1],[null,null],[120,3]],60,"M0.00 1.00 M120.00 3.00"],
 [[[60,1],[0,2]],60,"M60.00 1.00 M0.00 2.00"],
 [[[0,0],[60,0]],60,"M0.00 0.00 L60.00 0.00"]
];
for(const [points,step,expected] of cases){
 const actual=historySegmentedPath(points,x,y,step);
 if(actual!==expected)throw Error(JSON.stringify({points,actual,expected}));
}
console.log("FS1113_MISSING_SCRAPE_GAP=PASS");
"""
result = subprocess.run(["node", "-e", js], capture_output=True, text=True)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
