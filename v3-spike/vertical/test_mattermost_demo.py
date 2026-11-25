import unittest
from urllib.parse import urlencode
from mattermost_demo import command

class ChatOpsTest(unittest.TestCase):
    def test_command(self):
        token="x"*32
        core={"production_authorized":False,"run":{"run_id":"RUN-CI-X","incident_id":"INC-CI-X"}}
        context={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-X","policy":"DENY","affected":[],"evidence":[{"evidence_id":"E1","payload_hash":"a"*64}]}
        fields={"token":token,"channel_id":"lab","command":"/aiops","text":"incident"}
        def call():
            return command(urlencode(fields).encode(),token,"lab",core,context)
        result=call()
        self.assertEqual(result["response_type"],"ephemeral")
        self.assertIn("Root cause UNKNOWN",result["text"])
        self.assertIn("E1",result["text"])
        fields["text"]="execute"
        self.assertIn("DENY",call()["text"])
        fields["channel_id"]="other"
        with self.assertRaises(ValueError): call()
        fields["channel_id"]="lab"
        fields["token"]="wrong"
        with self.assertRaises(ValueError): call()

if __name__=="__main__": unittest.main()
