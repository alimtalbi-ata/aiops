import unittest
from int10c_process_policy import stop_owned

class FakeHandle:
    def __init__(self, identities, absence):
        self.identities=iter(identities)
        self.absence=iter(absence)
        self.calls=[]
    async def identity(self):
        return next(self.identities)
    async def terminate(self):
        self.calls.append("terminate")
    async def kill(self):
        self.calls.append("kill")
    async def absent(self):
        return next(self.absence)

class ProcessPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_graceful(self):
        h=FakeHandle(["owned"],[True])
        self.assertEqual(await stop_owned(h,expected_identity="owned",timeout=1),"ABSENCE_REPORTED")
        self.assertEqual(h.calls,["terminate"])
    async def test_escalation(self):
        h=FakeHandle(["owned","owned"],[False,True])
        self.assertEqual(await stop_owned(h,expected_identity="owned",timeout=1),"ABSENCE_REPORTED")
        self.assertEqual(h.calls,["terminate","kill"])
    async def test_foreign_or_replaced(self):
        for identities,absence,calls in [(["foreign"],[],[]),(["owned","foreign"],[False],["terminate"])]:
            h=FakeHandle(identities,absence)
            self.assertEqual(await stop_owned(h,expected_identity="owned",timeout=1),"IDENTITY_MISMATCH")
            self.assertEqual(h.calls,calls)
    async def test_absence_unconfirmed(self):
        h=FakeHandle(["owned","owned"],[False,False])
        self.assertEqual(await stop_owned(h,expected_identity="owned",timeout=1),"NOT_QUALIFIED")
