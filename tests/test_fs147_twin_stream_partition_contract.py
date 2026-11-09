"""FS147 candidate: strict, lossless offline demultiplexing of Twin receipts.

No live I/O. Synthetic adapter contract, not Debian E2E proof.
A consumer must not silently drop an unknown receipt or accept a partial RUN.
"""
import copy
import unittest

STAGES = ("event", "core", "critic", "policy", "worker", "evidence", "portal", "itsm")
IDENTITY = ("tenant_id", "graph", "namespace", "run_id")
LAB = dict(tenant_id="fixture-client-a", graph="filesystem-lab", namespace="fs-lab", run_id="RUN-FS147-FIXTURE")
SAN = dict(tenant_id="fixture-client-b", graph="twin-san", namespace="acme-san", run_id="RUN-SAN-FIXTURE")


def partition_receipts(receipts, expected=(LAB, SAN)):
    """Fail closed on unknown identities, duplicates, gaps or wrong order.

    Caller must run the full stage-level provenance/evidence validator on
    each returned trace. This function proves lossless routing only.
    """
    if not isinstance(receipts, list):
        raise ValueError("invalid receipt stream")
    keys = [tuple(item[field] for field in IDENTITY) for item in expected]
    if len(set(keys)) != len(keys):
        raise ValueError("ambiguous expected identities")
    groups = {key: [] for key in keys}
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError("malformed receipt")
        key = tuple(receipt.get(field) for field in IDENTITY)
        if key not in groups:
            raise ValueError("unknown or cross-graph identity")
        groups[key].append(copy.deepcopy(receipt))
    for key, trace in groups.items():
        if tuple(r.get("stage") for r in trace) != STAGES:
            raise ValueError("missing, duplicated or reordered RUN stage")
    return groups


def fixture(own):
    return [dict(**own, stage=stage, receipt_id=own["run_id"] + ":" + stage) for stage in STAGES]


class StreamPartitionContract(unittest.TestCase):
    def test_interleaved_lossless_deterministic_and_nonmutating(self):
        lab, san = fixture(LAB), fixture(SAN)
        mixed = [r for pair in zip(lab, san) for r in pair]
        snapshot = copy.deepcopy(mixed)
        first = partition_receipts(mixed)
        self.assertEqual(first[tuple(LAB[k] for k in IDENTITY)], lab)
        self.assertEqual(first[tuple(SAN[k] for k in IDENTITY)], san)
        self.assertEqual(partition_receipts(mixed), first)
        self.assertEqual(mixed, snapshot)

    def test_reject_unknown_and_forged_partial_identity(self):
        mixed = [r for pair in zip(fixture(LAB), fixture(SAN)) for r in pair]
        for key, value in (("tenant_id", "intruder"), ("graph", SAN["graph"]),
                           ("namespace", SAN["namespace"]), ("run_id", SAN["run_id"])):
            with self.subTest(field=key):
                poisoned = copy.deepcopy(mixed)
                poisoned[0][key] = value
                with self.assertRaisesRegex(ValueError, "unknown or cross-graph"):
                    partition_receipts(poisoned)

    def test_reject_missing_duplicate_and_reordered_stage(self):
        mixed = [r for pair in zip(fixture(LAB), fixture(SAN)) for r in pair]
        cases = (mixed[:-1], mixed + [copy.deepcopy(mixed[0])],
                 [mixed[2], mixed[1], mixed[0]] + mixed[3:])
        for poisoned in cases:
            with self.subTest(length=len(poisoned)):
                with self.assertRaisesRegex(ValueError, "missing, duplicated or reordered"):
                    partition_receipts(poisoned)

    def test_reject_ambiguous_expected_identity(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            partition_receipts([], expected=(LAB, copy.deepcopy(LAB)))


if __name__ == "__main__":
    unittest.main()
