"""FS147 regression: dependencies must not lie about SAN/FS ownership."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "fs"))
from fs147_twin_partition_gate import IsolationError, qualify


def capture():
    return (
        {"nodes": [
            {"node_id": "FS-1", "namespace": "lab-fs147"},
            {"node_id": "SAN-1", "namespace": "san"},
        ], "edges": [{
            "edge_id": "DEP-FS", "source_id": "FS-1",
            "target_id": "FS-1", "relation_type": "depends_on",
        }]},
        {"run_id": "RUN-FS", "synthetic": True, "facts": [{
            "fact_id": "FACT-FS", "node_id": "FS-1",
            "value": {"run_id": "RUN-FS", "synthetic": True, "target_node_id": "FS-1"},
        }]},
        {"run_id": "RUN-SAN", "synthetic": True, "facts": [{
            "fact_id": "FACT-SAN", "node_id": "SAN-1",
            "value": {"run_id": "RUN-SAN", "synthetic": True, "target_node_id": "SAN-1"},
        }]},
    )


def check(graph, fs, san):
    return qualify(graph, fs, san, "lab-fs147", "san", "RUN-FS", "RUN-SAN")


class DependencyProvenanceTest(unittest.TestCase):
    def test_unambiguous_dependency_is_accepted(self):
        graph, fs, san = capture()
        graph["edges"][0].update(namespace="lab-fs147",
                                 source_namespace="lab-fs147",
                                 target_namespace="lab-fs147")
        self.assertEqual(check(graph, fs, san)["status"], "PASS")

    def test_cross_namespace_dependency_metadata_is_rejected(self):
        for field in ("namespace", "source_namespace", "target_namespace"):
            with self.subTest(field=field):
                graph, fs, san = capture()
                graph["edges"][0][field] = "san"
                with self.assertRaisesRegex(IsolationError, "dependency provenance"):
                    check(graph, fs, san)

    def test_fact_synthetic_marker_requires_boolean_or_legacy_string(self):
        for marker in (True, "true", False, 1, 1.0, 0, None, "True", "false"):
            for encoded in (False, True):
                with self.subTest(marker=marker, encoded=encoded):
                    import json
                    graph, fs, san = capture()
                    payload = fs["facts"][0]["value"]
                    payload["synthetic"] = marker
                    if encoded:
                        fs["facts"][0]["value"] = json.dumps(payload)
                    if marker is True or marker == "true":
                        self.assertEqual(check(graph, fs, san)["status"], "PASS")
                    else:
                        with self.assertRaisesRegex(IsolationError, "unmarked observation"):
                            check(graph, fs, san)

    def test_embedded_observation_namespace_must_match_node_owner(self):
        import json
        for encoded in (False, True):
            for partition in (1, 2):
                for field in ("namespace", "source_namespace", "target_namespace"):
                    with self.subTest(encoded=encoded, partition=partition, field=field):
                        graph, fs, san = capture()
                        response = (None, fs, san)[partition]
                        payload = response["facts"][0]["value"]
                        payload[field] = "san" if partition == 1 else "lab-fs147"
                        if encoded:
                            response["facts"][0]["value"] = json.dumps(payload)
                        with self.assertRaisesRegex(IsolationError, "embedded observation provenance"):
                            check(graph, fs, san)

    def test_matching_embedded_observation_provenance_is_accepted(self):
        graph, fs, san = capture()
        fs["facts"][0]["value"].update(
            namespace="lab-fs147",
            source_namespace="lab-fs147",
            target_namespace="lab-fs147",
        )
        san["facts"][0]["value"]["namespace"] = "san"
        self.assertEqual(check(graph, fs, san)["status"], "PASS")

    def test_cross_namespace_dependency_endpoints_still_rejected(self):
        graph, fs, san = capture()
        graph["edges"][0]["target_id"] = "SAN-1"
        with self.assertRaisesRegex(IsolationError, "cross-namespace dependency"):
            check(graph, fs, san)


if __name__ == "__main__":
    unittest.main()
