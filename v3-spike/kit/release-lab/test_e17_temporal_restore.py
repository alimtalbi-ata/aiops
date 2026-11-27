import contextlib
import io
import json
import unittest

from e17_temporal_restore import canonical_schema, require_equal_snapshots


def column(name, position, default=None, kind="integer", udt="int4"):
    return {"table_name": "history_node", "column_name": name,
            "ordinal_position": position, "data_type": kind, "udt_name": udt,
            "is_nullable": "NO", "column_default": default}


def schema(columns):
    return json.dumps({"columns": columns, "constraints": [], "indexes": []})


def snapshot(columns, row_digest="sha256:" + "a" * 64):
    value = {"tables": {"history_node": {"rows": 1, "sha256": row_digest}}}
    value.update(canonical_schema(schema(columns)))
    return value


class TemporalRestoreSchemaTests(unittest.TestCase):
    def paired(self, before, after):
        return ({db: before for db in ("temporal", "temporal_visibility")},
                {db: after for db in ("temporal", "temporal_visibility")})

    def test_pg_dump_compacts_dropped_physical_ordinals_only(self):
        source = snapshot([column("id", 1), column("payload", 3)])
        restored = snapshot([column("id", 1), column("payload", 2)])
        self.assertEqual(source["schema_sha256"], restored["schema_sha256"])
        self.assertNotEqual(source["physical_ordinal_sha256"], restored["physical_ordinal_sha256"])
        before, after = self.paired(source, restored)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            require_equal_snapshots(before, after, "after_restore_before_server_start")
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["classification"], "V3_E17_TEMPORAL_PHYSICAL_ORDINAL_NORMALIZATION")
        self.assertEqual(receipt["result"], "PASS_LOGICAL_SCHEMA")

    def test_visible_column_order_change_is_rejected(self):
        source = snapshot([column("id", 1), column("payload", 3)])
        reordered = snapshot([column("payload", 1), column("id", 2)])
        self.assertNotEqual(source["schema_sha256"], reordered["schema_sha256"])
        before, after = self.paired(source, reordered)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "snapshot mismatch"):
            require_equal_snapshots(before, after, "after_restore_before_server_start")

    def test_column_default_change_is_rejected(self):
        source = snapshot([column("id", 1, "nextval('history_node_id_seq'::regclass)")])
        changed = snapshot([column("id", 1, "0")])
        self.assertNotEqual(source["schema_sha256"], changed["schema_sha256"])
        before, after = self.paired(source, changed)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "snapshot mismatch"):
            require_equal_snapshots(before, after, "after_restore_before_server_start")

    def test_row_digest_change_is_never_normalized(self):
        source = snapshot([column("id", 1)])
        changed = snapshot([column("id", 1)], "sha256:" + "b" * 64)
        before, after = self.paired(source, changed)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "snapshot mismatch"):
            require_equal_snapshots(before, after, "after_restore_before_server_start")

    def test_duplicate_column_identity_is_rejected(self):
        columns = [column("id", 1), column("id", 2)]
        with self.assertRaisesRegex(ValueError, "invalid physical column order"):
            canonical_schema(schema(columns))


if __name__ == "__main__":
    unittest.main()
