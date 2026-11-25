import unittest
from unittest.mock import Mock
from glpi_bridge import preview_ticket

class BridgeTest(unittest.TestCase):
    def test_binding(self):
        rid="RUN-CI-X"
        core={"production_authorized":False,"run":{"run_id":rid,"incident_id":"INC-CI-X","mode":"DEMO"}}
        context={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":rid,"policy":"DENY","affected":[],"evidence":[{"evidence_id":"E1","payload_hash":"a"*64}]}
        client=Mock()
        ticket={"id":1,"name":"[SYNTHETIC] "+rid,"is_deleted":0}
        followup={"id":2,"items_id":1,"itemtype":"Ticket","content":"@copilot incident"}
        client.read_ticket.return_value=(ticket,[followup])
        def call(tid=1,fid=2):
            return preview_ticket(client,tid,fid,core,context,synthetic_ticket_id=1,synthetic_run_id=rid)
        with self.assertRaises(ValueError): call(3)
        client.read_ticket.assert_not_called()
        result=call()
        self.assertFalse(result["posted"])
        self.assertEqual(result["input"]["is_private"],1)
        self.assertIn("E1",result["input"]["content"])
        self.assertEqual(result["operational_decision"],"DENY")
        with self.assertRaises(ValueError): call(fid=3)
        client.read_ticket.return_value=(ticket,[followup,followup])
        with self.assertRaises(ValueError): call()
        client.read_ticket.return_value=(dict(ticket,name="ordinary"),[followup])
        with self.assertRaises(ValueError): call()
        core["run"]["mode"]="LIVE"
        with self.assertRaises(ValueError): call()
if __name__=="__main__": unittest.main()
