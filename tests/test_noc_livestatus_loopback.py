import socket
import threading
import unittest
from demo.noc_livestatus_loopback import collect_loopback_hosts,QUERY
T="2026-10-24T20:00:00Z"
NOW="2026-10-24T20:01:00Z"
def fake_server(response):
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(("127.0.0.1",0));sock.listen(1)
    port=sock.getsockname()[1]
    def serve():
        try:
            peer,_=sock.accept()
            with peer:
                command=peer.recv(2048)
                assert command==QUERY,command
                peer.sendall(response)
        finally:sock.close()
    thread=threading.Thread(target=serve,daemon=True);thread.start()
    return port,thread
class LoopbackLivestatusTests(unittest.TestCase):
    def test_real_socket_read_only_query(self):
        port,thread=fake_server(b'[["name","state","plugin_output"],["brocade-fc01",2,"synthetic port CRIT"]]')
        result=collect_loopback_hosts(host="127.0.0.1",port=port,captured_at=T,now_utc=NOW)
        thread.join(2)
        self.assertEqual(result["hosts"]["brocade-fc01"]["state"],"CRIT")
        self.assertEqual(result["collection_transport"],"TCP_LOOPBACK_ONLY")
        self.assertFalse(result["runtime_authenticated"])
    def test_remote_target_refused(self):
        with self.assertRaises(ValueError):
            collect_loopback_hosts(host="10.79.94.202",port=6557,captured_at=T,now_utc=NOW)
    def test_invalid_header_refused(self):
        port,thread=fake_server(b'[["wrong"],["x"]]')
        with self.assertRaises(ValueError):
            collect_loopback_hosts(host="127.0.0.1",port=port,captured_at=T,now_utc=NOW)
        thread.join(2)
    def test_no_empty_acceptance(self):
        port,thread=fake_server(b'[["name","state","plugin_output"]]')
        with self.assertRaises(ValueError):
            collect_loopback_hosts(host="127.0.0.1",port=port,captured_at=T,now_utc=NOW)
        thread.join(2)
if __name__=="__main__":unittest.main()
