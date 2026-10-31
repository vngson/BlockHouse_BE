import tempfile
import unittest
from pathlib import Path
from local_web import create_web_app


class LocalWebTests(unittest.TestCase):
    def test_only_frontend_files_are_exposed_with_security_headers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'assets').mkdir()
            (root / 'index.html').write_text('<html>BlockHouse</html>')
            (root / 'assets' / 'app.js').write_text('/* frontend */')
            (root / 'BlockHouse.db').write_text('private')
            client = create_web_app(root).test_client()
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('BlockHouse', response.text)
            self.assertEqual(response.headers['Cache-Control'], 'no-cache')
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
            self.assertIn('http://127.0.0.1:5050', response.headers['Content-Security-Policy'])
            response.close()
            with client.get('/assets/app.js') as asset:
                self.assertIn('javascript', asset.content_type)
            for path in ['/BlockHouse.db', '/assets/../BlockHouse.db', '/assets/%2e%2e/BlockHouse.db', '/api/web/session']:
                self.assertEqual(client.get(path).status_code, 404, path)
            self.assertEqual(client.get('/', base_url='http://untrusted.example:8080').status_code, 403)
