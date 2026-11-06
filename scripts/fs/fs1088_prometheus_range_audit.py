#!/usr/bin/env python3
"""FS1088: read-only Prometheus range-query readiness audit."""
import datetime,json,os,pathlib,subprocess,sys,time,urllib.parse
PORTAL="aiops2-rebuild-portal"
PROM="http://aiops2-rebuild-prometheus:9090"
QUERIES={"availability":"up","scrape_duration":"scrape_duration_seconds"}
def docker(*args):
 p=subprocess.run(["docker",*args],capture_output=True,text=True,timeout=20)
 if p.returncode:raise RuntimeError("docker command failed: "+p.stderr[-240:])
 return p.stdout.strip()
def query(expr,start,end,step):
 url=PROM+"/api/v1/query_range?"+urllib.parse.urlencode({"query":expr,"start":start,"end":end,"step":step})
 script="import sys,urllib.request;print(urllib.request.urlopen(sys.argv[1],timeout=12).read(4000000).decode())"
 data=json.loads(docker("exec",PORTAL,"python3","-c",script,url))
 if data.get("status")!="success":raise RuntimeError("Prometheus query_range not successful: "+str(data.get("error","unknown"))[:140])
 return data.get("data",{})
def main():
 state=json.loads(docker("inspect",PORTAL))[0]
 assert state["State"]["Running"],"portal not running"
 end=int(time.time())
 start=end-3600
 stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
 directory=pathlib.Path.home()/".local/state/aiops-debian-agent/prometheus"/("fs1088-"+stamp)
 directory.mkdir(mode=0o700,parents=True,exist_ok=False)
 report={"mode":"READ_ONLY","window_seconds":3600,"step_seconds":60,"queries":{}}
 for name,expr in QUERIES.items():
  data=query(expr,start,end,60)
  assert data.get("resultType")=="matrix","expected matrix result"
  series=data.get("result",[])
  counts=[len(x.get("values",[])) for x in series]
  labels=[{"job":x.get("metric",{}).get("job",""),"instance":x.get("metric",{}).get("instance","")} for x in series]
  report["queries"][name]={"expression":expr,"series":len(series),"samples_total":sum(counts),"samples_min":min(counts,default=0),"samples_max":max(counts,default=0),"labels":labels}
  print("FS1088_QUERY="+name+" SERIES="+str(len(series))+" SAMPLES="+str(sum(counts))+" MIN="+str(min(counts,default=0))+" MAX="+str(max(counts,default=0)),flush=True)
  assert series and sum(counts)>0,"no history for "+name
  assert all(count>=2 for count in counts),"insufficient samples for "+name
 path=directory/"report.json"
 path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 os.chmod(path,0o600)
 print("FS1088_REPORT="+str(path),flush=True)
 print("FS1088_RESULT=PASS",flush=True)
 print("FS1088_PRODUCTION_MUTATION=NONE",flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("FS1088_RESULT=FAIL "+type(e).__name__+": "+str(e)[:260],flush=True)
  sys.exit(1)
