import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).resolve().parents[1] / "deploy" / "backup-inventory.py"
spec = importlib.util.spec_from_file_location("backup_inventory", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def fixture():
    vols = [x[1] for x in module.REQUIRED.values()] + list(module.OTHER_VOLUMES)
    return {"services": {s: {"volumes": [{"source": v, "target": "/data"}]}
                         for s, (_, v) in module.REQUIRED.items()},
            "volumes": {v: {"name": v} for v in vols}}

class BackupInventoryTests(unittest.TestCase):
    def test_complete(self):
        result = module.assess(fixture())
        self.assertEqual(result["status"], "READY_FOR_OPERATOR_REVIEW")
        self.assertEqual(len(result["database_services"]), 3)
        self.assertNotIn("BACKUP_VERIFIED", result["qualification"])
    def test_missing_db_blocks(self):
        cfg = fixture()
        del cfg["services"]["aiops2-glpi-db"]
        self.assertEqual(module.assess(cfg)["status"], "BLOCKED")
    def test_missing_volume_mapping_blocks(self):
        cfg = fixture()
        cfg["services"]["aiops2-postgres"]["volumes"] = []
        self.assertIn("volume_mapping:aiops2-postgres:aiops2-postgres-data", module.assess(cfg)["missing"])
    def test_missing_persistent_volume_blocks(self):
        cfg = fixture()
        del cfg["volumes"]["aiops2-n8n-data"]
        self.assertEqual(module.assess(cfg)["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
