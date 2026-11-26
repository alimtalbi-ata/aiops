"""Disposable loopback service: measure real latency in an explicitly synthetic scenario."""
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import statistics
import threading
import time
import uuid

class LabApplication(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        if self.path!="/health":
            self.send_error(404)
            return
        time.sleep(self.server.delay)
        self.send_response(200)
        self.send_header("Content-Length","2")
        self.end_headers()
        self.wfile.write(b"OK")

def observed_batch():
    with HTTPServer(("127.0.0.1",0),LabApplication) as app:
        if app.server_port in (7770,7777,7790):
            raise RuntimeError("protected port")
        app.delay=0.01
        worker=threading.Thread(target=app.serve_forever,daemon=True)
        worker.start()
        samples={}
        try:
            for phase,delay in (("baseline",0.01),("incident",0.15)):
                app.delay=delay
                timings=[]
                for _ in range(5):
                    conn=http.client.HTTPConnection("127.0.0.1",app.server_port,timeout=2)
                    try:
                        start=time.perf_counter_ns()
                        conn.request("GET","/health")
                        response=conn.getresponse()
                        body=response.read()
                        elapsed=(time.perf_counter_ns()-start)/1e6
                        if response.status!=200 or body!=b"OK":
                            raise RuntimeError("lab application unavailable")
                        timings.append(round(elapsed,3))
                    finally:
                        conn.close()
                samples[phase]=timings
        finally:
            app.shutdown()
            worker.join(5)
    medians={phase:round(statistics.median(values),3) for phase,values in samples.items()}
    if not 0<medians["baseline"]<medians["incident"]/2:
        raise RuntimeError("controlled slowdown not demonstrated")
    identity=uuid.uuid4().hex
    common={"kind":"metric","source":"observed-loopback-http","resource":"NODE-CI-ROOT","severity":"critical","tenant":"synthetic-demo","synthetic":True}
    batch=[{**common,"id":identity+"-"+phase,"observation":{"metric":"latency_ms","phase":phase,"value":value}} for phase,value in medians.items()]
    return batch,{"classification":"MEASURED_SYNTHETIC_LAB","samples_ms":samples,"median_ms":medians,"method":"five HTTP requests per phase; monotonic wall-clock duration","production_authorized":False}

if __name__=="__main__":
    import json
    batch,receipt=observed_batch()
    print(json.dumps({"batch":batch,"measurement":receipt}))
