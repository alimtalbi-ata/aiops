import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError
from http_demo import server

class CoreHttpTests(unittest.TestCase):
    def test_projection_and_failure(self):
        config=(18081,"x"*32,"RUN-01")
        with server(core_config=config) as http:
            worker=threading.Thread(target=http.serve_forever,daemon=True)
            worker.start()
            url="http://127.0.0.1:%d/api/v1/core-run" % http.server_port
            try:
                projection={"classification":"SYNTHETIC_CANONICAL_RUN","policy":"DENY"}
                with patch("http_demo.read_run",return_value=projection) as read:
                    with urlopen(url,timeout=5) as response:
                        self.assertEqual(json.load(response),projection)
                    read.assert_called_once_with(*config)
                with patch("http_demo.read_run",side_effect=ValueError("secret")):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(url,timeout=5)
                    self.assertEqual(caught.exception.code,503)
                    self.assertNotIn(b"secret",caught.exception.read())
                http.core_config=None
                with self.assertRaises(HTTPError) as caught:
                    urlopen(url,timeout=5)
                self.assertEqual(caught.exception.code,503)
            finally:
                http.shutdown()
                worker.join(5)
