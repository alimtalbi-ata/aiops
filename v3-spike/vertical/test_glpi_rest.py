import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from glpi_rest import LabGLPI

class RestTest(unittest.TestCase):
    def test_session(self):
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path,self.headers.get("App-Token"),self.headers.get("Session-Token"),self.headers.get("Authorization")))
                path=self.path.split("/apirest.php/")[-1]
                if path=="Ticket/2":
                    self.send_response(302)
                    self.send_header("Location","http://127.0.0.1:7770/")
                    self.end_headers()
                    return
                data={"initSession":{"session_token":"s"*32},"Ticket/1":{"id":1},"Ticket/1/ITILFollowup?range=0-19":[{"id":2}],"killSession":{}}[path]
                body=json.dumps(data).encode()
                self.send_response(206 if 'ITILFollowup' in path else 200)
                self.send_header("Content-Length",str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        with ThreadingHTTPServer(("127.0.0.1",0),Handler) as http:
            thread=threading.Thread(target=http.serve_forever,daemon=True)
            thread.start()
            try:
                with LabGLPI(http.server_port,"a"*32,"u"*32) as client:
                    self.assertEqual(client.read_ticket(1),({"id":1},[{"id":2}]))
                    with self.assertRaises(HTTPError): client.read_ticket(2)
                self.assertIsNone(client.session)
                self.assertEqual(len(calls),5)
                self.assertEqual(calls[0][3],"user_token "+"u"*32)
                self.assertTrue(all(c[1]=="a"*32 for c in calls))
                self.assertTrue(all(c[2]=="s"*32 for c in calls[1:]))
                self.assertTrue(calls[-1][0].endswith("killSession"))
            finally:
                http.shutdown()
                thread.join(5)
        for port in (7770,7777,7790):
            with self.assertRaises(ValueError): LabGLPI(port,"a"*32,"u"*32)
if __name__=="__main__": unittest.main()
