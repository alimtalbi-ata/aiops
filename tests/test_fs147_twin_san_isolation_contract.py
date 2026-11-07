"""FS147 / Twin SAN: fixture-only isolation contract; no Docker, network or host effects."""
import copy
import unittest

LAB = {
    "graph": "filesystem-lab", "namespace": "fs-lab", "incident_id": "147",
    "run_id": "RUN-FS147-FIXTURE", "evidence_id": "EVID-FS147-FIXTURE",
    "observations": [{"source": "filesystem-sanity-check", "mount": "/fs-lab",
                      "metric": "aiops2_fs_lab_used_percent", "value": 92}],
    "dependencies": [{"from": "RUN-FS147-FIXTURE", "to": "EVID-FS147-FIXTURE"}],
}
SAN = {
    "graph": "twin-san", "namespace": "acme-san", "incident_id": "SAN-FIXTURE",
    "run_id": "RUN-SAN-FIXTURE", "evidence_id": "EVID-SAN-FIXTURE",
    "observations": [{"source": "Twin-Simulator", "fabric": "ACME-SAN-FABRIC-A"}],
    "dependencies": [{"from": "RUN-SAN-FIXTURE", "to": "EVID-SAN-FIXTURE"}],
}
IDENTITY = ("graph", "namespace", "incident_id", "run_id", "evidence_id")
SAN_MARKERS = ("twin-san", "twin-simulator", "acme-san", "acme-san-fabric-a",
               "run-san-fixture", "evid-san-fixture")
LAB_MARKERS = ("filesystem-lab", "fs-lab", "run-fs147-fixture",
               "evid-fs147-fixture")


def strings(value):
    """Include nested keys as well as values: aliases cannot hide in metadata."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def assert_isolated(lab, san):
    """Validate explicit identity, observations and graph edges, fail closed."""
    if any(lab.get(k) != LAB[k] or san.get(k) != SAN[k] for k in IDENTITY):
        raise ValueError("graph/namespace/incident/RUN/Evidence identity mismatch")
    if set(lab[k] for k in IDENTITY) & set(san[k] for k in IDENTITY):
        raise ValueError("shared graph identity")
    if not lab.get("observations") or not san.get("observations"):
        raise ValueError("missing observations")
    for graph, own, foreign in ((lab, LAB, SAN_MARKERS), (san, SAN, LAB_MARKERS)):
        if graph.get("dependencies") != own["dependencies"]:
            raise ValueError("unexpected dependency edge")
        for token in strings(graph):
            lower = token.lower()
            if any(marker in lower for marker in foreign):
                raise ValueError("cross-domain contamination")
    if not any(obs.get("mount") == "/fs-lab" for obs in lab["observations"]):
        raise ValueError("missing lab mount evidence")
    if not any(obs.get("metric") == "aiops2_fs_lab_used_percent" and obs.get("source") == "filesystem-sanity-check" for obs in lab["observations"]):
        raise ValueError("missing filesystem metric provenance")
    # Inspect nested metadata too: a top-level-only check permits evidence laundering.
    if any(token == "aiops2_fs_lab_used_percent" for token in strings(san["observations"])):
        raise ValueError("filesystem metric in SAN")
    if any(not isinstance(obs, dict) or obs.get("source") != "filesystem-sanity-check" or obs.get("mount") != "/fs-lab" or obs.get("metric") != "aiops2_fs_lab_used_percent" for obs in lab["observations"]):
        raise ValueError("unqualified filesystem observation")
    if any("fabric" in obs for obs in lab["observations"]):
        raise ValueError("SAN observation in lab")
    if any("mount" in obs for obs in san["observations"]):
        raise ValueError("filesystem observation in SAN")
    # A filesystem producer can be laundered through SAN metadata without a mount or metric.
    if any(token.lower() == "filesystem-sanity-check" for token in strings(san["observations"])):
        raise ValueError("filesystem source in SAN")


class TwinSanIsolationContract(unittest.TestCase):
    def test_disjoint_fixture_graphs(self):
        assert_isolated(copy.deepcopy(LAB), copy.deepcopy(SAN))

    def test_reject_cross_graph_edge(self):
        lab = copy.deepcopy(LAB)
        lab["dependencies"].append({"from": lab["run_id"], "to": SAN["evidence_id"]})
        with self.assertRaises(ValueError):
            assert_isolated(lab, SAN)

    def test_reject_san_observation_nested_metadata(self):
        lab = copy.deepcopy(LAB)
        lab["observations"][0]["metadata"] = {"Twin-Simulator": {"fabric": "ACME-SAN-FABRIC-A"}}
        with self.assertRaises(ValueError):
            assert_isolated(lab, SAN)

    def test_reject_foreign_run_or_evidence(self):
        for key in ("run_id", "evidence_id", "namespace", "graph", "incident_id"):
            with self.subTest(key=key):
                lab = copy.deepcopy(LAB)
                lab[key] = SAN[key]
                with self.assertRaises(ValueError):
                    assert_isolated(lab, SAN)

    def test_reject_lab_reference_in_san(self):
        san = copy.deepcopy(SAN)
        san["observations"][0]["metadata"] = {"source_run": LAB["run_id"]}
        with self.assertRaises(ValueError):
            assert_isolated(LAB, san)

    def test_reject_missing_observation(self):
        lab = copy.deepcopy(LAB)
        lab["observations"] = []
        with self.assertRaises(ValueError):
            assert_isolated(lab, SAN)

    def test_reject_lab_metric_provenance_substitution(self):
        for field, value in (("metric", "san_latency"), ("source", "unknown")):
            with self.subTest(field=field):
                lab = copy.deepcopy(LAB)
                lab["observations"][0][field] = value
                with self.assertRaises(ValueError):
                    assert_isolated(lab, SAN)

    def test_reject_filesystem_metric_in_san(self):
        san = copy.deepcopy(SAN)
        san["observations"][0]["metric"] = "aiops2_fs_lab_used_percent"
        with self.assertRaises(ValueError):
            assert_isolated(LAB, san)

    def test_reject_nested_filesystem_metric_in_san(self):
        san = copy.deepcopy(SAN)
        san["observations"][0]["metadata"] = {"metric": "aiops2_fs_lab_used_percent"}
        with self.assertRaises(ValueError):
            assert_isolated(LAB, san)

    def test_reject_extra_unqualified_lab_observation(self):
        lab = copy.deepcopy(LAB)
        lab["observations"].append({"source": "unknown", "mount": "/fs-lab", "metric": "san_latency"})
        with self.assertRaises(ValueError):
            assert_isolated(lab, SAN)

    def test_reject_nested_filesystem_source_in_san(self):
        san = copy.deepcopy(SAN)
        san["observations"][0]["metadata"] = {"producer": "filesystem-sanity-check"}
        with self.assertRaises(ValueError):
            assert_isolated(LAB, san)

    def test_allow_filesystem_sanity_source(self):
        assert_isolated(LAB, SAN)


if __name__ == "__main__":
    unittest.main()
