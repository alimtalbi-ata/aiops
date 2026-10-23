"""No-network, synthetic adversarial tests for the STAR HTTP request fence."""
import unittest
from dataclasses import replace
from demo.star_browser_request_fence import ReadOnlyRequestPolicy, canonical_origin

ORIGIN = "http://127.0.0.1:55677"
PAGE = ORIGIN + "/executions/EXEC-39"
ASSET = ORIGIN + "/assets/safe.css"


class RequestFenceTests(unittest.TestCase):
    def policy(self):
        return ReadOnlyRequestPolicy(PAGE, ORIGIN)

    def permits(self, policy, url=PAGE, method="GET", navigation=True,
                main_frame=True, resource_type="document"):
        return policy.permits(url=url, method=method, navigation=navigation,
                              main_frame=main_frame, resource_type=resource_type)

    def test_exact_main_document_get_only(self):
        self.assertTrue(self.permits(self.policy()))
        for url in (PAGE + "?x=1", PAGE + "/extra", ORIGIN + "/executions/EXEC-40"):
            self.assertFalse(self.permits(self.policy(), url=url))

    def test_post_and_secondary_frame_rejected(self):
        self.assertFalse(self.permits(self.policy(), method="POST"))
        self.assertFalse(self.permits(self.policy(), main_frame=False))

    def test_same_origin_get_not_implicitly_safe(self):
        self.assertFalse(self.permits(self.policy(), url=ORIGIN + "/api/delete?id=1",
                                      navigation=False, resource_type="fetch"))

    def test_explicit_get_subresource_allowlist(self):
        p = replace(self.policy(), reviewed_get_urls=(ASSET,))
        self.assertTrue(self.permits(p, url=ASSET, navigation=False, resource_type="stylesheet"))
        self.assertFalse(self.permits(p, url=ASSET, navigation=True))
        self.assertFalse(self.permits(p, url=ASSET, method="POST", navigation=False,
                                      resource_type="stylesheet"))

    def test_cross_origin_and_credentials_rejected(self):
        for url in ("https://evil.invalid/", "http://user:pass@127.0.0.1:55677/",
                    PAGE + "#secret", "http://127.0.0.1:55677\\@evil.invalid/"):
            self.assertFalse(self.permits(self.policy(), url=url))

    def test_duplicate_and_cross_origin_allowlist_fail_closed(self):
        for urls in ((ASSET, ASSET), ("https://evil.invalid/x",), (PAGE,)):
            p = replace(self.policy(), reviewed_get_urls=urls)
            with self.assertRaises(ValueError):
                p.validate()
            self.assertFalse(self.permits(p))

    def test_canonical_origin(self):
        self.assertEqual(canonical_origin(PAGE), ORIGIN)
        with self.assertRaises(ValueError):
            canonical_origin("ftp://127.0.0.1:55677/secret")


if __name__ == "__main__":
    unittest.main()
