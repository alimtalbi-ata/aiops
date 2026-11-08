"""FS147: deterministic cross-stage evidence receipt boundary, candidate only.

Synthetic fixtures; no network, Docker, GLPI or database access.
This is an integration contract test, NOT a Debian E2E receipt.
"""
import copy
import unittest

from test_fs147_twin_adapter_boundary_contract import LAB, SAN, qualify_pair
from test_fs147_twin_nested_provenance_contract import reject_foreign_provenance

STAGES = ("event", "core", "critic", "policy", "worker", "evidence", "portal", "itsm")
IDENTITY = ("tenant_id", "graph", "namespace", "incident_id", "run_id",
            "evidence_ref", "source_event_id", "correlation_id")


def qualify_trace(trace, own, foreign):
    """Check provenance at every boundary; fail closed on missing/mixed stages."""
    if not isinstance(trace, list) or len(trace) != len(STAGES):
        raise ValueError("incomplete E2E stage trace")
    for expected_stage, receipt in zip(STAGES, trace):
        if not isinstance(receipt, dict) or receipt.get("stage") != expected_stage:
            raise ValueError("missing or reordered E2E stage")
        for key in IDENTITY:
            if receipt.get(key) != own[key]:
                raise ValueError("E2E identity drift: " + key)
        if receipt.get("dependencies") != own["dependencies"]:
            raise ValueError("E2E dependency drift")
        # An empty, missing or mutated observation must not count as an E2E receipt.
        # This is a synthetic contract, not a claim about the live API schema.
        if receipt.get("observations") != {"source_event_id": own["source_event_id"]}:
            raise ValueError("E2E observation drift")
        if receipt.get("receipt_id") != own["run_id"] + ":" + expected_stage:
            raise ValueError("E2E receipt replay or substitution")
        reject_foreign_provenance(receipt, foreign)
    return {"fixture": "QUALIFIED", "debian_e2e": "UNVERIFIED"}


def synthetic_trace(own):
    return [
        dict(stage=stage, receipt_id=own["run_id"] + ":" + stage,
             **{key: own[key] for key in IDENTITY},
             dependencies=copy.deepcopy(own["dependencies"]),
             observations={"source_event_id": own["source_event_id"]})
        for stage in STAGES
    ]


class TwinCrossStageReceiptContract(unittest.TestCase):
    def test_deterministic_bidirectional_isolation(self):
        qualify_pair(copy.deepcopy(LAB), copy.deepcopy(SAN))
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            trace = synthetic_trace(own)
            snapshot = copy.deepcopy(trace)
            self.assertEqual(qualify_trace(trace, own, foreign),
                             {"fixture": "QUALIFIED", "debian_e2e": "UNVERIFIED"})
            self.assertEqual(trace, snapshot)

    def test_foreign_evidence_in_any_stage_fails_closed(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            for index, stage in enumerate(STAGES):
                with self.subTest(graph=own["graph"], stage=stage):
                    trace = synthetic_trace(own)
                    trace[index]["observations"]["evidence"] = foreign["evidence_ref"]
                    with self.assertRaisesRegex(ValueError, "foreign"):
                        qualify_trace(trace, own, foreign)

    def test_missing_reordered_or_drifted_stage_rejected(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            trace = synthetic_trace(own)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                qualify_trace(trace[:-1], own, foreign)
            swapped = copy.deepcopy(trace)
            swapped[2], swapped[3] = swapped[3], swapped[2]
            with self.assertRaisesRegex(ValueError, "reordered"):
                qualify_trace(swapped, own, foreign)
            for key in IDENTITY:
                with self.subTest(graph=own["graph"], key=key):
                    drift = copy.deepcopy(trace)
                    drift[5][key] = foreign[key]
                    with self.assertRaisesRegex(ValueError, "identity drift"):
                        qualify_trace(drift, own, foreign)

    def test_missing_or_mutated_observation_rejected_at_every_stage(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            for index, stage in enumerate(STAGES):
                for mutation in (None, {}, {"source_event_id": "unrelated"}):
                    with self.subTest(graph=own["graph"], stage=stage, mutation=mutation):
                        trace = synthetic_trace(own)
                        if mutation is None:
                            trace[index].pop("observations")
                        else:
                            trace[index]["observations"] = mutation
                        with self.assertRaisesRegex(ValueError, "observation drift"):
                            qualify_trace(trace, own, foreign)

    def test_receipt_replay_or_missing_receipt_id_rejected(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            for index, stage in enumerate(STAGES):
                for replacement in (None, own["run_id"] + ":event", foreign["run_id"] + ":" + stage):
                    if replacement == own["run_id"] + ":" + stage:
                        continue
                    with self.subTest(graph=own["graph"], stage=stage, replacement=replacement):
                        trace = synthetic_trace(own)
                        if replacement is None:
                            trace[index].pop("receipt_id")
                        else:
                            trace[index]["receipt_id"] = replacement
                        with self.assertRaisesRegex(ValueError, "receipt replay"):
                            qualify_trace(trace, own, foreign)

    def test_cross_graph_dependency_at_portal_rejected(self):
        for own, foreign in ((LAB, SAN), (SAN, LAB)):
            trace = synthetic_trace(own)
            trace[6]["dependencies"].append(
                {"from": own["run_id"], "to": foreign["evidence_ref"]})
            with self.assertRaises(ValueError):
                qualify_trace(trace, own, foreign)


if __name__ == "__main__":
    unittest.main()
