"""FS147 adapter ingress: reject nested SAN provenance leaks before Core ingestion.

Candidate-only, standard library, no live I/O. Complements fixture equality tests.
"""
import copy
import unittest
from urllib.parse import unquote, urlsplit, parse_qsl

from test_fs147_twin_adapter_boundary_contract import LAB, SAN, qualify_pair

IDENTITY_KEYS = frozenset({
    "tenant_id", "graph", "namespace", "incident_id", "run_id",
    "evidence_ref", "source_event_id", "correlation_id", "payload_ref",
})
NESTED_KEYS = frozenset({"observations", "metadata", "dependencies", "resource", "links"})


def reject_foreign_provenance(envelope, foreign):
    """Fail closed on foreign identifiers anywhere in structured adapter payload.

    Values are compared as complete strings, not substrings. A malformed graph
    or cycle fails closed. Never interprets fixture IDs as real GLPI records.
    """
    foreign_ids = {foreign[k] for k in IDENTITY_KEYS if isinstance(foreign.get(k), str)}
    seen = set()

    def check_string(value, path):
        # Decode bounded layers to catch nested URI encoding without unbounded work.
        # Match whole identity tokens, never substrings of ordinary prose.
        decoded = value
        for _ in range(4):
            if decoded in foreign_ids:
                raise ValueError("foreign SAN/FS provenance at " + "/".join(path))
            parts = urlsplit(decoded)
            if parts.scheme in {"http", "https", "urn"}:
                tokens = parts.path.replace(":", "/").split("/")
                tokens += [key for key, _ in parse_qsl(parts.query, keep_blank_values=True)]
                tokens += [val for _, val in parse_qsl(parts.query, keep_blank_values=True)]
                tokens += parts.fragment.replace(":", "/").split("/")
                if any(token in foreign_ids for token in tokens):
                    raise ValueError("foreign SAN/FS provenance in URI at " + "/".join(path))
            next_decoded = unquote(decoded)
            if next_decoded == decoded:
                break
            decoded = next_decoded

    def walk(value, path):
        if isinstance(value, (dict, list)):
            obj_id = id(value)
            if obj_id in seen:
                raise ValueError("cyclic or aliased adapter payload")
            seen.add(obj_id)
            if isinstance(value, dict):
                for key, item in value.items():
                    if isinstance(key, str):
                        check_string(key, path + ("<key>",))
                    walk(item, path + (str(key),))
            else:
                for index, item in enumerate(value):
                    walk(item, path + (str(index),))
        elif isinstance(value, str):
            check_string(value, path)

    walk(envelope, ())


class TwinIngressNestedIsolation(unittest.TestCase):
    def test_clean_nested_lab_and_san_replay(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            event = copy.deepcopy(own)
            event["observations"] = [{"metric": own["metric"], "value": 42}]
            event["metadata"] = {"trace": {"source_event_id": own["source_event_id"]}}
            reject_foreign_provenance(event, foreign)
        self.assertEqual(qualify_pair(copy.deepcopy(LAB), copy.deepcopy(SAN))["live_fs147"], "UNKNOWN")

    def test_nested_foreign_identity_rejected_in_both_directions(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            for field in sorted(IDENTITY_KEYS):
                with self.subTest(direction=own["graph"], field=field):
                    event = copy.deepcopy(own)
                    event["metadata"] = {"trace": [{"provenance": {field: foreign[field]}}]}
                    with self.assertRaisesRegex(ValueError, "foreign SAN/FS provenance"):
                        reject_foreign_provenance(event, foreign)

    def test_foreign_dependency_observation_and_link_rejected(self):
        for key, value in (
            ("dependencies", [{"from": LAB["run_id"], "to": SAN["evidence_ref"]}]),
            ("observations", [{"source_event_id": SAN["source_event_id"]}]),
            ("links", [{"target": {"graph": SAN["graph"]}}]),
        ):
            with self.subTest(key=key):
                event = copy.deepcopy(LAB)
                event[key] = value
                with self.assertRaises(ValueError):
                    reject_foreign_provenance(event, SAN)

    def test_uri_encoded_foreign_provenance_rejected(self):
        from urllib.parse import quote
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            for carrier in (
                "https://example.invalid/evidence/" + quote(foreign["evidence_ref"], safe=""),
                "https://example.invalid/trace?run=" + quote(foreign["run_id"], safe=""),
                "urn:trace:" + foreign["source_event_id"],
            ):
                with self.subTest(graph=own["graph"], carrier=carrier):
                    event = copy.deepcopy(own)
                    event["metadata"] = {"uri": carrier}
                    with self.assertRaisesRegex(ValueError, "foreign SAN/FS provenance"):
                        reject_foreign_provenance(event, foreign)

    def test_nested_uri_encoding_query_key_and_fragment_tokens_rejected(self):
        from urllib.parse import quote
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            foreign_run = foreign["run_id"]
            for carrier in (
                "https://example.invalid/trace?" + quote(foreign_run, safe="") + "=1",
                "https://example.invalid/trace#section/" + foreign_run,
                "https://example.invalid/trace?run=" + quote(quote(foreign_run, safe=""), safe=""),
                "https://example.invalid/trace#ref:" + foreign_run,
            ):
                with self.subTest(graph=own["graph"], carrier=carrier):
                    event = copy.deepcopy(own)
                    event["metadata"] = {"uri": carrier}
                    with self.assertRaisesRegex(ValueError, "foreign SAN/FS provenance"):
                        reject_foreign_provenance(event, foreign)

    def test_unrelated_prose_and_uri_allowed(self):
        event = copy.deepcopy(LAB)
        event["metadata"] = {"note": "prefix-" + SAN["run_id"] + "-suffix", "uri": "https://example.invalid/trace?run=unrelated"}
        reject_foreign_provenance(event, SAN)

    def test_foreign_identity_in_nested_mapping_key_rejected(self):
        # JSON object keys are provenance carriers too, including URI-encoded keys.
        from urllib.parse import quote
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            for key in (foreign["run_id"],
                        "https://example.invalid/ref/" + quote(foreign["evidence_ref"], safe="")):
                with self.subTest(graph=own["graph"], key=key):
                    event = copy.deepcopy(own)
                    event["metadata"] = {"lookup": {key: "present"}}
                    with self.assertRaisesRegex(ValueError, "foreign SAN/FS provenance"):
                        reject_foreign_provenance(event, foreign)

    def test_cycle_fails_closed(self):
        event = copy.deepcopy(LAB)
        event["metadata"] = {}
        event["metadata"]["self"] = event["metadata"]
        with self.assertRaisesRegex(ValueError, "cyclic"):
            reject_foreign_provenance(event, SAN)


if __name__ == "__main__":
    unittest.main()
