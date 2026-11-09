import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('supervisor', Path(__file__).with_name('supervisor.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Safety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patches = [patch.object(m, 'RUN', self.root),
                        patch.object(m, 'LOCK', self.root / 'lock'),
                        patch.object(m, 'STOP', self.root / 'STOP')]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in self.patches: p.stop()
        self.tmp.cleanup()
    def test_expired_never_spawns(self):
        with patch.object(m, 'DEADLINE', time.time()-1), patch.object(m.subprocess, 'Popen') as spawn:
            self.assertEqual(m.run(), 0)
            spawn.assert_not_called()
        self.assertEqual(json.loads((self.root/'state.json').read_text())['status'], 'expired')
    def test_nested_context_never_spawns(self):
        with patch.object(m, 'DEADLINE', time.time()+30), patch.object(m, 'host_blocker', return_value='nested'), patch.object(m.subprocess, 'Popen') as spawn:
            self.assertEqual(m.run(), 78)
            spawn.assert_not_called()
        self.assertEqual(json.loads((self.root/'state.json').read_text())['first_cycle'], 'NOT_STARTED')
    def test_unique_lock(self):
        with (self.root/'lock').open('a') as lock:
            m.fcntl.flock(lock, m.fcntl.LOCK_EX | m.fcntl.LOCK_NB)
            with patch.object(m.subprocess, 'Popen') as spawn:
                self.assertEqual(m.run(), 73)
                spawn.assert_not_called()
    def test_stop_never_spawns(self):
        (self.root/'STOP').touch()
        with patch.object(m, 'DEADLINE', time.time()+30), patch.object(m, 'host_blocker', return_value=None), patch.object(m.subprocess, 'Popen') as spawn:
            self.assertEqual(m.run(), 0)
            spawn.assert_not_called()
    def test_cycle_timeout_spacing_and_deadline_with_real_sleep(self):
        real_popen = m.subprocess.Popen
        starts = []
        children = []
        def spawn(command, **kwargs):
            self.assertEqual(command[:2], ['timeout', '--signal=KILL'])
            self.assertIn('workspace-write', command)
            self.assertIn('sandbox_workspace_write.network_access=true', command)
            starts.append(time.monotonic())
            child = real_popen(['/bin/sleep', '30'], **kwargs)
            children.append(child)
            return child
        with patch.object(m, 'DEADLINE', time.time()+0.65), patch.object(m, 'INTERVAL', 0.3), patch.object(m, 'CYCLE_LIMIT', 0.05), patch.object(m, 'host_blocker', return_value=None), patch.object(m.subprocess, 'Popen', side_effect=spawn):
            self.assertEqual(m.run(), 0)
        self.assertGreaterEqual(len(starts), 2)
        self.assertTrue(all(b-a >= 0.29 for a,b in zip(starts, starts[1:])))
        self.assertTrue(all(c.poll() is not None for c in children))
        self.assertEqual(json.loads((self.root/'state.json').read_text())['status'], 'expired')

    def test_group_killed_and_reaped(self):
        from unittest.mock import Mock
        child = Mock(pid=123456)
        with patch.object(m.os, 'killpg') as kill:
            m.kill_group(child)
        kill.assert_called_once_with(123456, m.signal.SIGKILL)
        child.wait.assert_called_once()

if __name__ == '__main__': unittest.main()
