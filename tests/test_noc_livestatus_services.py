import socket
import threading
import unittest
from demo.noc_livestatus_services import SERVICES_QUERY,parse_services,collect_loopback_services
T="2026-10-24T20:00:00Z"
NOW="2026-10-24T20:01:00Z"
ROWS=[["host_name","description","state","plugin_output"],
      ["brocade-fc01","FC port 8/16",2,"synthetic CRIT"],
      ["brocade-fc01","FC ISL",1,"synthetic WARN"]]
class LivestatusServicesTests(unittest.TestCase):
    def test_multiple_services_on_same_host(self):
        result=parse_services(ROWS,captured_at=T,now_utc=NOW)
        self.assertEqual(len(result["services"]),2)
        self.assertEqual(result["services"][0]["state"],"CRIT")
        self.assertFalse(result["runtime_authenticated"])
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):parse_services(ROWS+[ROWS[1]],captured_at=T,now_utc=NOW)
    def test_stale_rejected(self):
        with self.assertRaises(ValueError):parse_services(ROWS,captured_at=T,now_utc="2026-10-24T21:00:00Z")
    def test_loopback_wire_query(self):
        listener=socket.socket();listener.bind(("127.0.0.1",0));listener.listen(1)
        port=listener.getsockname()[1];seen=[]
        def serve():
            with listener:
                peer,_=listener.accept()
                with peer:
                    seen.append(peer.recv(1024))
                    peer.sendall(b'[["host_name","description","state","plugin_output"],["brocade-fc01","FC port",2,"synthetic"]]')
        worker=threading.Thread(target=serve,daemon=True);worker.start()
        result=collect_loopback_services(host="127.0.0.1",port=port,captured_at=T,now_utc=NOW)
        worker.join(2)
        self.assertEqual(seen,[SERVICES_QUERY])
        self.assertEqual(result["services"][0]["state"],"CRIT")
    def test_remote_blocked(self):
        with self.assertRaises(ValueError):collect_loopback_services(host="10.79.94.202",port=6557,captured_at=T,now_utc=NOW)
if __name__=="__main__":unittest.main()
