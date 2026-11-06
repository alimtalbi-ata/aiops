"""FS147 E2E read-only correlation gate; fixture-only, no host or API calls.

This is deliberately NOT an adapter: it rejects unrelated runs/evidence and
cannot approve remediation. Feed only real snapshots once host access exists.
"""
import unittest

LEGACY_RUN = "RUN-4FABD1786F107E51"
LEGACY_EVIDENCE = "EVD-D2069BA816126499"
SAN = "ACME-SAN-FABRIC-A"


def contains_san_reference(value):
    """Reject SAN identifiers even when nested in filesystem evidence."""
    if isinstance(value, str):
        normalized = value.casefold().strip()
        return SAN.casefold() in normalized or "twin-simulator" in normalized
    if isinstance(value, dict):
        return any(contains_san_reference(k) or contains_san_reference(v)
                   for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_san_reference(item) for item in value)
    return False


def check_fs147_chain(ticket, run, evidence):
    """Fail closed unless ticket 147, run and filesystem evidence agree."""
    if not all(isinstance(x, dict) for x in (ticket, run, evidence)):
        return False
    rid = run.get("run_id")
    eid = evidence.get("evidence_id")
    provenance = evidence.get("provenance")
    payload = evidence.get("payload")
    if (str(ticket.get("id")) != "147" or not isinstance(rid, str)
            or not rid.strip() or rid == LEGACY_RUN or not isinstance(eid, str)
            or not eid.strip() or eid == LEGACY_EVIDENCE
            or not isinstance(provenance, dict)
            or not isinstance(payload, dict)):
        return False
    if str(run.get("glpi_ticket_id")) != "147":
        return False
    if provenance.get("run_id") != rid or str(provenance.get("glpi_ticket_id")) != "147":
        return False
    # If the Evidence API exposes redundant linkage fields, they must not
    # contradict the authoritative provenance/run/ticket correlation.
    if ("run_id" in evidence and evidence["run_id"] != rid) or (
            "glpi_ticket_id" in evidence and str(evidence["glpi_ticket_id"]) != "147"):
        return False
    if payload.get("filesystem") != "/fs-lab":
        return False
    if (not isinstance(evidence.get("source"), str)
            or not evidence["source"].strip()
            or "twin" in evidence["source"].lower()
            or "san" in evidence["source"].lower()
            or payload.get("node_id") == SAN):
        return False
    if (contains_san_reference(ticket) or contains_san_reference(run)
            or contains_san_reference(provenance) or contains_san_reference(payload)
            or contains_san_reference(evidence)):
        return False
    # Presence of a receipt alone is not an observed filesystem measurement.
    used = payload.get("used_percent")
    if (isinstance(used, bool) or not isinstance(used, (int, float))
            or not 0 <= used <= 100):
        return False
    if any(not isinstance(evidence.get(k), str) or not evidence[k].strip()
           for k in ("payload_hash", "observed_at")):
        return False
    return True


class FS147ChainContract(unittest.TestCase):
    def setUp(self):
        # Invented identifiers ONLY as negative/positive test fixtures.
        self.ticket = {"id": 147}
        self.run = {"run_id": "RUN-TEST-147", "glpi_ticket_id": 147}
        self.evidence = {
            "evidence_id": "EVD-TEST-147", "source": "filesystem-detector",
            "payload_hash": "sha256:fixture", "observed_at": "2026-11-06T00:00:00Z",
            "provenance": {"run_id": "RUN-TEST-147", "glpi_ticket_id": 147},
            "payload": {"filesystem": "/fs-lab", "used_percent": 92},
        }

    def test_fixture_consistent(self):
        self.assertTrue(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_legacy_v28_run_and_evidence_rejected(self):
        self.run["run_id"] = LEGACY_RUN
        self.evidence["evidence_id"] = LEGACY_EVIDENCE
        self.evidence["provenance"]["run_id"] = LEGACY_RUN
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_wrong_ticket_and_run_rejected(self):
        self.ticket["id"] = 146
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.ticket["id"] = 147
        self.evidence["provenance"]["run_id"] = "RUN-OTHER"
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_san_and_missing_measurement_rejected(self):
        self.evidence["source"] = "twin-simulator"
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.evidence["source"] = "filesystem-detector"
        self.evidence["payload"]["node_id"] = SAN
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.evidence["payload"].pop("node_id")
        self.evidence["payload"]["filesystem"] = "/"
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_nested_san_contamination_rejected(self):
        self.evidence["payload"]["details"] = {
            "observations": [{"asset": " ACME-SAN-FABRIC-A "}]
        }
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.evidence["payload"].pop("details")
        self.evidence["provenance"]["collector"] = ["Twin-Simulator"]
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_san_in_run_or_ticket_metadata_rejected(self):
        self.run["context"] = {"asset": ["ACME-SAN-FABRIC-A"]}
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.run.pop("context")
        self.ticket["context"] = {"origin": "Twin-Simulator"}
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_san_in_other_evidence_metadata_rejected(self):
        # The API may add envelope fields outside payload/provenance.
        self.evidence["context"] = {"upstream": ["ACME-SAN-FABRIC-A"]}
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.evidence.pop("context")
        self.evidence["collector_details"] = {"name": "Twin-Simulator"}
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_san_in_evidence_metadata_key_rejected(self):
        self.evidence["ACME-SAN-FABRIC-A"] = "untrusted"
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_conflicting_evidence_top_level_links_rejected(self):
        self.evidence["run_id"] = "RUN-OTHER"
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.evidence["run_id"] = self.run["run_id"]
        self.evidence["glpi_ticket_id"] = 146
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.evidence["glpi_ticket_id"] = 147
        self.assertTrue(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_blank_run_and_evidence_ids_rejected(self):
        self.run["run_id"] = "   "
        self.evidence["provenance"]["run_id"] = "   "
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.run["run_id"] = "RUN-TEST-147"
        self.evidence["provenance"]["run_id"] = "RUN-TEST-147"
        self.evidence["evidence_id"] = "   "
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_missing_or_invalid_measurement_rejected(self):
        self.evidence["payload"].pop("used_percent")
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        for invalid in ("92", True, -1, 101, None):
            self.evidence["payload"]["used_percent"] = invalid
            self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_blank_receipt_metadata_rejected(self):
        self.evidence["payload_hash"] = "   "
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))
        self.evidence["payload_hash"] = "sha256:fixture"
        self.evidence["observed_at"] = "   "
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))

    def test_no_receipt_or_timestamp_is_not_proof(self):
        self.evidence.pop("observed_at")
        self.assertFalse(check_fs147_chain(self.ticket, self.run, self.evidence))


if __name__ == "__main__":
    unittest.main()
