import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Isolate the CMS DB before importing its seed-on-startup module.
ROOT = Path(__file__).resolve().parents[1]
_TMP = tempfile.mkdtemp(prefix="eddy-portfolio-test-")
os.environ["PORTFOLIO_DB"] = str(Path(_TMP) / "test.db")
os.environ["PORTFOLIO_PUBLIC_READONLY"] = "1"
from fastapi.testclient import TestClient
import app as portfolio

class PortfolioReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(portfolio.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        shutil.rmtree(_TMP, ignore_errors=True)

    def test_pages_assets_and_game_preserved(self):
        for route in ('/', '/index.html', '/projects.html', '/cyberlab.html', '/about.html', '/contact.html', '/styles.css', '/script.js', '/EDDY_BIEGON_CV.docx'):
            self.assertEqual(self.client.get(route).status_code, 200, route)
        html=self.client.get('/').text
        self.assertIn('Packet Defender', html)
        self.assertIn('nexusdesk-demo.onrender.com', html)
        self.assertIn('securescan-demo.onrender.com', html)

    def test_both_projects_publicly_featured(self):
        r=self.client.get('/api/projects')
        self.assertEqual(r.status_code, 200)
        data=r.json()
        self.assertTrue(any('NexusDesk' in p['title'] and p['featured'] for p in data))
        self.assertTrue(any('SecureScan' in p['title'] and p['featured'] for p in data))
        self.assertTrue(any(p['title'] == 'KNLS Website' for p in data))
        self.assertTrue(any(p['title'] == 'Mint Dental Centre' for p in data))

    def test_public_admin_locked(self):
        for path in ('/admin', '/admin/login', '/admin/setup', '/api/admin/all', '/api/admin/projects'):
            self.assertEqual(self.client.get(path).status_code, 404, path)
            self.assertEqual(self.client.post(path).status_code, 404, path)

    def test_health_readonly(self):
        self.assertEqual(self.client.get('/health').json(), {'status':'ok','read_only':True})
        self.assertEqual(self.client.get('/').headers.get('x-content-type-options'), 'nosniff')

if __name__ == '__main__': unittest.main()
