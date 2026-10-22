import sys,unittest,datetime
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"/"core"))
from denial_fencing import validate_finalization

UTC=datetime.timezone.utc

class FencingValidationTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.datetime.now(UTC)
        self.row=dict(
            status="PENDING",lease_owner="worker-B",
            fencing_token=2,
            lease_expires_at=self.now+datetime.timedelta(seconds=60),
            run_status="BLOCKED",critic_validated=False)
        self.verdict=dict(state="BLOCKED",decision="HUMAN_APPROVAL")

    def check_rejected(self,reason):
        with self.assertRaisesRegex(ValueError,reason):
            validate_finalization(self.row,"worker-B",2,
                                  self.verdict,self.now)

    def test_valid_owner(self):
        self.assertTrue(validate_finalization(
            self.row,"worker-B",2,self.verdict,self.now))

    def test_stale_token(self):
        self.row["fencing_token"]=3
        self.check_rejected("stale_fencing_token")

    def test_expired_lease(self):
        self.row["lease_expires_at"]=self.now
        self.check_rejected("lease_expired")

    def test_unblocked_run(self):
        self.row["run_status"]="RUNNING"
        self.check_rejected("critic_denial_not_verified")

    def test_validated_critic(self):
        self.row["critic_validated"]=True
        self.check_rejected("critic_denial_not_verified")

    def test_unsafe_policy(self):
        self.verdict["decision"]="ALLOW"
        self.check_rejected("unsafe_policy_verdict")
