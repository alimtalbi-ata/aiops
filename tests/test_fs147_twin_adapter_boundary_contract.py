"""FS147 Twin adapter boundary: deterministic, offline, standard-library-only tests.

Proposed contract, not an assertion about Debian APIs or live incident 147.
"""
import copy
import unittest

LAB = {
    "schema_version": "candidate.v1", "tenant_id": "fixture-client-a",
    "source_system": "filesystem-sanity-check", "source_event_id": "FS147-FIXTURE-EVENT",
    "observed_at": "2026-11-06T10:00:00Z", "received_at": "2026-11-06T10:00:01Z",
    "correlation_id": "FS147-FIXTURE-CORR", "payload_ref": "fixture://fs-lab/measurement",
    "evidence_ref": "EVID-FS147-FIXTURE", "graph": "filesystem-lab",
    "namespace": "fs-lab", "incident_id": "147-FIXTURE",
    "run_id": "RUN-FS147-FIXTURE", "metric": "aiops2_fs_lab_used_percent",
    "resource": "/fs-lab", "dependencies": [
        {"from": "RUN-FS147-FIXTURE", "to": "EVID-FS147-FIXTURE"}
    ],
}
SAN = {
    "schema_version": "candidate.v1", "tenant_id": "fixture-client-b",
    "source_system": "Twin-Simulator", "source_event_id": "SAN-FIXTURE-EVENT",
    "observed_at": "2026-11-06T10:00:00Z", "received_at": "2026-11-06T10:00:01Z",
    "correlation_id": "SAN-FIXTURE-CORR", "payload_ref": "fixture://san/fabric",
    "evidence_ref": "EVID-SAN-FIXTURE", "graph": "twin-san",
    "namespace": "acme-san", "incident_id": "SAN-FIXTURE",
    "run_id": "RUN-SAN-FIXTURE", "metric": "san_latency",
    "resource": "ACME-SAN-FABRIC-A", "dependencies": [
        {"from": "RUN-SAN-FIXTURE", "to": "EVID-SAN-FIXTURE"}
    ],
}
FIELDS = ("tenant_id", "source_system", "source_event_id", "correlation_id",
          "payload_ref", "evidence_ref", "graph", "namespace", "incident_id",
          "run_id", "metric", "resource")
ENVELOPE = ("schema_version", "tenant_id", "source_system", "source_event_id",
            "observed_at", "received_at", "correlation_id", "payload_ref",
            "evidence_ref")


def qualify_pair(lab, san):
    """Reject missing provenance, swapped identities and foreign graph edges."""
    for actual, expected in ((lab, LAB), (san, SAN)):
        if any(not actual.get(field) for field in ENVELOPE):
            raise ValueError("incomplete adapter envelope")
        if any(actual.get(field) != expected[field] for field in FIELDS):
            raise ValueError("adapter identity/provenance mismatch")
        if actual.get("dependencies") != expected["dependencies"]:
            raise ValueError("foreign or missing dependency")
        if actual.get("observed_at") != expected["observed_at"]:
            raise ValueError("non-deterministic observation")
        if actual.get("received_at") != expected["received_at"]:
            raise ValueError("non-deterministic receipt")
    if set(lab[field] for field in FIELDS) & set(san[field] for field in FIELDS):
        raise ValueError("cross-tenant identity collision")
    return {"lab": "QUALIFIED_FIXTURE", "san": "QUALIFIED_FIXTURE",
            "live_fs147": "UNKNOWN", "twin_required_for_fs147": "UNVERIFIED"}


class AdapterBoundaryContract(unittest.TestCase):
    def test_deterministic_replay_without_live_effects(self):
        first = qualify_pair(copy.deepcopy(LAB), copy.deepcopy(SAN))
        second = qualify_pair(copy.deepcopy(LAB), copy.deepcopy(SAN))
        self.assertEqual(first, second)
        self.assertEqual(first["live_fs147"], "UNKNOWN")

    def test_reject_swapped_identity_and_provenance(self):
        for field in FIELDS:
            with self.subTest(field=field):
                lab = copy.deepcopy(LAB)
                lab[field] = SAN[field]
                with self.assertRaises(ValueError):
                    qualify_pair(lab, SAN)

    def test_reject_cross_tenant_dependency(self):
        lab = copy.deepcopy(LAB)
        lab["dependencies"].append({"from": LAB["run_id"], "to": SAN["evidence_ref"]})
        with self.assertRaises(ValueError):
            qualify_pair(lab, SAN)

    def test_reject_missing_envelope_fields(self):
        for field in ENVELOPE:
            with self.subTest(field=field):
                lab = copy.deepcopy(LAB)
                lab.pop(field)
                with self.assertRaises(ValueError):
                    qualify_pair(lab, SAN)

    def test_reject_nondeterministic_observation(self):
        lab = copy.deepcopy(LAB)
        lab["observed_at"] = "2026-11-06T10:01:00Z"
        with self.assertRaises(ValueError):
            qualify_pair(lab, SAN)


if __name__ == "__main__":
    unittest.main()
