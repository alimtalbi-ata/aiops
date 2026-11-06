#!/usr/bin/env python3
"""FS1087: read-only Prometheus time-series capability discovery."""
import datetime,json,os,pathlib,subprocess,sys,urllib.parse,urllib.request
NAME="aiops2-rebuild-prometheus"
queries={
 "availability":"up",
 "scrape_duration":"scrape_duration_seconds",
 "cpu_usage":"rate(process_cpu_seconds_total[5m])",
 "memory_rss":"process_resident_memory_bytes",
 "host_cpu":"rate(node_cpu_seconds_total{mode=\"idle\"}[5m])",
 "host_memory":"node_memory_MemAvailable_bytes",
 "http_requests":"http_requests_total",
 "http_latency":"http_request_duration_seconds_bucket",
 "container_cpu":"rate(container_cpu_usage_seconds_total[5m])",
 "container_memory":"container_memory_working_set_bytes",
}
def docker(*args):
 p=subprocess.run(["docker",*args],text=True,capture_output=True,timeout=12)
 if p.returncode:raise RuntimeError("docker "+args[0]+" failed: "+p.stderr[-180:])
 return p.stdout.strip()
def fetch(path,params=None):
 url="http://127.0.0.1:9090"+path
 if params:url+="?"+urllib.parse.urlencode(params)
 raw=docker("exec",NAME,"python3","-c", "import urllib.request,sys;print(urllib.request.urlopen(sys.argv[1],timeout=7).read(2000000).decode())",url)
 obj=json.loads(raw)
 if obj.get("status")!="success":raise RuntimeError("Prometheus returned non-success")
 return obj["data"]
def main():
 info=json.loads(docker("inspect",NAME))[0]
 assert info["State"]["Running"],"Prometheus not running"
 stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
 out=pathlib.Path.home()/".local/state/aiops-debian-agent/prometheus"/("fs1087-"+stamp)
 out.mkdir(parents=True,mode=0o700,exist_ok=False)
 targets=fetch("/api/v1/targets",{"state":"active"})
 active=targets.get("activeTargets",[])
 print("FS1087_TARGETS="+str(len(active)),flush=True)
 for t in active:
  print("FS1087_TARGET job="+str(t.get("labels",{}).get("job","?"))+" health="+str(t.get("health","?")),flush=True)
 results={}
 for label,expr in queries.items():
  try:
   data=fetch("/api/v1/query",{"query":expr})
   series=data.get("result",[])
   results[label]={"expression":expr,"series_count":len(series),"sample_labels":[{k:v for k,v in item.get("metric",{}).items() if k in ("job","instance","mode","method","handler")} for item in series[:3]]}
   print("FS1087_METRIC="+label+" SERIES="+str(len(series)),flush=True)
  except Exception as e:
   results[label]={"expression":expr,"error":type(e).__name__+": "+str(e)[:120]}
   print("FS1087_METRIC="+label+" ERROR="+type(e).__name__,flush=True)
 report={"mode":"READ_ONLY","targets":len(active),"metrics":results}
 file=out/"report.json"
 file.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 os.chmod(file,0o600)
 print("FS1087_REPORT="+str(file),flush=True)
 print("FS1087_RESULT=PASS",flush=True)
 print("FS1087_PRODUCTION_MUTATION=NONE",flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("FS1087_RESULT=FAIL "+type(e).__name__+": "+str(e)[:240],flush=True)
  sys.exit(1)
