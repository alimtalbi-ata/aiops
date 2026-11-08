"""FS147 adapter ingress: reject nested SAN provenance leaks before Core ingestion.

Candidate-only, standard library, no live I/O. Complements fixture equality tests.
"""
import copy
import unittest

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

    def walk(value, path):
        if isinstance(value, (dict, list)):
            obj_id = id(value)
            if obj_id in seen:
                raise ValueError("cyclic or aliased adapter payload")
            seen.add(obj_id)
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, path + (str(key),))
            else:
                for index, item in enumerate(value):
                    walk(item, path + (str(index),))
        elif isinstance(value, str) and value in foreign_ids:
            raise ValueError("foreign SAN/FS provenance at " + "/".join(path))

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

    def test_cycle_fails_closed(self):
        event = copy.deepcopy(LAB)
        event["metadata"] = {}
        event["metadata"]["self"] = event["metadata"]
        with self.assertRaisesRegex(ValueError, "cyclic"):
            reject_foreign_provenance(event, SAN)


if __name__ == "__main__":
    unittest.main()
