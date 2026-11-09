"""Offline installation in a temporary home; never invokes Docker or a remote host."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

PATH=Path(__file__).resolve().parents[2]/'scripts/ops/install_live_usecase_12min.py'
spec=importlib.util.spec_from_file_location('usecase_installer_bundle',PATH)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA='a'*40

class BundleInstallationTests(unittest.TestCase):
    def test_all_tools_pinned_backed_up_and_probe_hold_propagated(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            root=home/'aiops2-audit-tools'
            root.mkdir()
            (root/'run_linkage_gate.py').write_text('# prior source\n')
            with patch.object(m.Path,'home',return_value=home), \
                 patch.object(m,'fetch_pinned',return_value=b'# qualified source\n') as fetch, \
                 patch.object(m.subprocess,'run',return_value=Mock(returncode=2,stdout='',stderr='')) as probe, \
                 patch('sys.argv',['installer','--commit',SHA]):
                self.assertEqual(m.main(),2)
            self.assertEqual(fetch.call_args_list[0].args,(SHA,))
            self.assertEqual([call.args for call in fetch.call_args_list[1:]],
                             [(SHA,source) for source in m.DEPENDENCIES])
            self.assertIn('--tools',probe.call_args.args[0])
            self.assertIn(str(root),probe.call_args.args[0])
            receipts=list((home/'aiops2-release-receipts').glob('usecase-install-*.json'))
            receipt=json.loads(receipts[0].read_text())
            self.assertEqual(receipt['cron'],'SKIPPED')
            self.assertEqual(len(receipt['installed_tools']),4)
            for tool in receipt['installed_tools']:
                self.assertEqual(len(tool['sha256']),64)
                self.assertEqual(Path(tool['installed_path']).read_bytes(),b'# qualified source\n')
                self.assertEqual(Path(tool['installed_path']).stat().st_mode & 0o777,0o700)
            backup=next(t['backup_path'] for t in receipt['installed_tools']
                        if t['source_path'].endswith('run_linkage_gate.py'))
            self.assertEqual(Path(backup).read_text(),'# prior source\n')

    def test_dependency_fetch_failure_preserves_all_existing_tools(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            root=home/'aiops2-audit-tools'
            root.mkdir()
            target=root/'live_usecase_qualification.py'
            target.write_text('# old\n')
            with patch.object(m.Path,'home',return_value=home), \
                 patch.object(m,'fetch_pinned',side_effect=[b'# new\n',RuntimeError('unavailable')]), \
                 patch.object(m.subprocess,'run') as probe, \
                 patch('sys.argv',['installer','--commit',SHA]):
                with self.assertRaises(RuntimeError):
                    m.main()
            probe.assert_not_called()
            self.assertEqual(target.read_text(),'# old\n')
            self.assertEqual(list(root.iterdir()),[target])

if __name__=='__main__':
    unittest.main()
