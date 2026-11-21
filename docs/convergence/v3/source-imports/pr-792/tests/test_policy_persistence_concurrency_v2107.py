"""V2.10.7: isolated persistence, concurrency and read-only observability."""
import concurrent.futures,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"app"))
from policy import autonomy_store as store
from policy.execution_fence import reserve,summary,decisions

class PersistenceAndConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=store.PATH
        store.PATH=Path(self.tmp.name)/"policy.sqlite3"
    def tearDown(self):
        store.PATH=self.old
        self.tmp.cleanup()
    def test_persisted_across_separate_sqlite_connections(self):
        first=store.set_mode("STOP_AUTO","operator","Safe stop retained after restart",0)
        self.assertEqual(first["revision"],1)
        # Open a new connection, representing a new process reading the same volume.
        with store._connect() as db:
            self.assertEqual(db.execute("SELECT mode FROM mode_history ORDER BY revision DESC LIMIT 1").fetchone()[0],"STOP_AUTO")
        self.assertEqual(store.status()["revision"],1)
        self.assertEqual(store.history()[0]["reason"],"Safe stop retained after restart")
    def test_concurrent_revision_change_only_one_winner(self):
        def commit(i):
            try:
                return store.set_mode("STOP_AUTO","operator",f"Emergency change by concurrent operator {i}",0)["revision"]
            except RuntimeError:
                return "CONFLICT"
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(commit,range(8)))
        self.assertEqual(results.count(1),1)
        self.assertEqual(results.count("CONFLICT"),7)
        self.assertEqual(len(store.history()),1)
    def test_concurrent_admissions_at_most_one(self):
        store.set_mode("NORMAL","operator","Normal simulated operations qualification",0)
        def attempt(_):return reserve("same-operation",1,"STANDARD_CHANGE")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes=list(pool.map(attempt,range(8)))
        self.assertEqual(sum(x["admitted"] for x in outcomes),1)
        self.assertEqual(summary()["reservations_recorded"],1)
        self.assertEqual(summary()["refusals_recorded"],7)
    def test_stop_after_reservation_blocks_stale_next_step(self):
        store.set_mode("NORMAL","operator","Test admission before emergency change",0)
        initial=reserve("step-one",1,"AUTONOMOUS_REMEDIATION")
        self.assertTrue(initial["admitted"])
        self.assertFalse(initial["execution_allowed"])
        store.set_mode("STOP_AUTO","operator","Emergency stop during pending workflow",1)
        latest=reserve("step-two",1,"AUTONOMOUS_REMEDIATION")
        self.assertFalse(latest["admitted"])
        self.assertEqual(latest["reason"],"STALE_POLICY_REVISION")
    def test_policy_kpi_audit_consistency(self):
        reserve("blocked",0,"AUTONOMOUS_REMEDIATION")
        reserve("stale",9,"STANDARD_CHANGE")
        records=decisions()
        self.assertEqual(len(records),2)
        self.assertEqual(summary()["refusals_recorded"],2)
        self.assertEqual(summary()["reservations_recorded"],0)

if __name__=="__main__":unittest.main()
