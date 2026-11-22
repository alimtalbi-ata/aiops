"""Offline Chromium qualification for the isolated NOC prototype; no LIVE calls."""
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / 'docs/ux/prototypes/noc_decision_sandbox_20261116.html'

class NocPrototypeBrowser(unittest.TestCase):
    def test_responsive_decision_and_no_network(self):
        self.assertTrue(PROTOTYPE.is_file(), f'missing exact source: {PROTOTYPE}')
        with TemporaryDirectory() as output, sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            manifest = []
            for width in (320, 768, 1440):
                page = browser.new_page(viewport={'width':width,'height':900}, device_scale_factor=1)
                requests = []
                page.route('**/*', lambda route: (requests.append(route.request.url), route.abort()))
                page.set_content(PROTOTYPE.read_text(encoding='utf-8'), wait_until='load')
                body = page.locator('body')
                for label in ('Alertes corrélées', "Chemin d'impact estimé", 'Preuves et incertitudes', 'Analyst / Critic', 'Policy / HITL', 'Prochaine action NOC'):
                    self.assertEqual(page.get_by_role('heading', name=label).count(), 1)
                self.assertIn('DENY_LIVE', body.inner_text())
                self.assertIn('UNKNOWN', body.inner_text())
                self.assertIn('SIMULATION ISOLÉE', body.inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                self.assertEqual(requests, [])
                page.get_by_role('button', name='Préparer un constat local').click()
                self.assertIn('Aucune transmission', page.get_by_role('status').inner_text())
                self.assertEqual(requests, [])
                path = Path(output) / f'noc-{width}.png'
                page.screenshot(path=str(path), full_page=True)
                manifest.append({'width':width,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size_bytes':path.stat().st_size})
                page.close()
            browser.close()
            self.assertEqual(len(manifest),3)
            print(json.dumps({'mode':'SIMULATION','source':'local exact file','captures':manifest,'live':'DENY_LIVE'},ensure_ascii=False))

if __name__ == '__main__':
    unittest.main()
