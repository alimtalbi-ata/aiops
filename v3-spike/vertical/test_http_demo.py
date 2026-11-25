import json
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
from http_demo import server
from vertical_demo import verify_projection

class HttpDemoTests(unittest.TestCase):
    def test_http_projection(self):
        with server() as http:
            worker = threading.Thread(target=http.serve_forever, daemon=True)
            worker.start()
            base = "http://127.0.0.1:%d" % http.server_port
            try:
                for suffix, decision in [("", "DENY"), ("?simulate=1", "SIMULATE_ONLY")]:
                    with urlopen(base + "/api/v1/demo" + suffix, timeout=5) as response:
                        result = json.load(response)
                    self.assertTrue(verify_projection(result))
                    self.assertEqual(result["policy"]["decision"], decision)
                    self.assertFalse(result["run"]["executed_on_host"])
                with urlopen(base + "/", timeout=5) as response:
                    self.assertIn(b"http-deny", response.read())
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "/api/v1/demo?simulate=true", timeout=5)
                self.assertEqual(error.exception.code, 404)
            finally:
                http.shutdown()
                worker.join(5)

if __name__ == "__main__":
    unittest.main()
