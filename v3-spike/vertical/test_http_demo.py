import json
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
from http_demo import server, EVENT
from correlation_demo import correlate
from vertical_demo import verify_projection

class HttpDemoTests(unittest.TestCase):
    def test_correlation_boundaries(self):
        second = {**EVENT, "id": "synthetic-002"}
        result = correlate([EVENT, second, EVENT])
        self.assertEqual(result, correlate([second, EVENT]))
        self.assertEqual(result["incidents"][0]["alert_count"], 2)
        self.assertEqual(len(correlate([EVENT, {**second, "tenant": "other"}])["incidents"]), 2)
        self.assertEqual(len(correlate([EVENT, {**second, "resource": "other"}])["incidents"]), 2)
        with self.assertRaises(ValueError):
            correlate([EVENT, {**EVENT, "severity": "warning"}])

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
                with urlopen(base + "/api/v1/incidents", timeout=5) as response:
                    incident, = json.load(response)["incidents"]
                self.assertEqual(incident["alert_count"], 2)
                self.assertEqual(len(incident["evidence"]), 2)
                self.assertEqual(incident["rca"]["status"], "UNKNOWN")
                self.assertEqual(incident["policy"], "DENY")
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
