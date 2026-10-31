"""Exercise real Waitress startup, data isolation, file locks and Windows shutdown."""
import ctypes
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from uuid import uuid4
from ctypes import wintypes


@unittest.skipUnless(os.name == 'nt', 'Windows event integration')
class RuntimeProcessTests(unittest.TestCase):
    def test_installed_paths_backup_lock_and_graceful_shutdown(self):
        self.exercise()

    def test_busy_web_port_keeps_api_available(self):
        self.exercise(web_busy=True)

    def exercise(self, web_busy=False):
        app = Path(__file__).resolve().parent.parent / 'app.py'
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with socket.socket() as port_socket:
                port_socket.bind(('127.0.0.1', 0))
                port = port_socket.getsockname()[1]
            with socket.socket() as web_socket:
                web_socket.bind(('127.0.0.1', 0))
                web_port = web_socket.getsockname()[1]
            if web_busy:
                busy = socket.socket()
                self.addCleanup(busy.close)
                busy.bind(('127.0.0.1', web_port))
                busy.listen()
            event = 'Local\\BlockHouseAudit-' + uuid4().hex
            env = dict(os.environ, BLOCKHOUSE_STOP_EVENT=event)
            executable = os.getenv('BLOCKHOUSE_TEST_EXE')
            command = ([executable] if executable else [sys.executable, '-B', str(app)]) + ['--data-dir', folder, '--port', str(port), '--web-port', str(web_port)]
            process = subprocess.Popen(command, cwd=folder, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                def get_health():
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/web/health', timeout=1) as response:
                            return json.load(response)
                    except (OSError, urllib.error.URLError):
                        return None
                until = time.monotonic() + 20
                while not get_health() and time.monotonic() < until:
                    if process.poll() is not None: self.fail('BE exited before health check')
                    time.sleep(0.1)
                self.assertEqual(get_health(), {'app': 'BlockHouse', 'api_version': 2})
                web_root = (Path(executable).parent if executable else app.parent) / 'web'
                if executable:
                    self.assertTrue((web_root / 'index.html').is_file(), 'Packaged BE must include its web folder')
                if (web_root / 'index.html').is_file() and not web_busy:
                    with urllib.request.urlopen(f'http://127.0.0.1:{web_port}/', timeout=3) as response:
                        html = response.read().decode()
                        self.assertIn('<title>BlockHouse</title>', html)
                        self.assertIn("style-src-attr 'unsafe-inline'", response.headers['Content-Security-Policy'])
                    request = urllib.request.Request(f'http://127.0.0.1:{port}/api/web/session', headers={'Origin':f'http://127.0.0.1:{web_port}'})
                    with urllib.request.urlopen(request, timeout=3) as response:
                        self.assertEqual(response.headers['Access-Control-Allow-Origin'], f'http://127.0.0.1:{web_port}')
                    asset = html.split('src="')[1].split('"')[0]
                    with urllib.request.urlopen(f'http://127.0.0.1:{web_port}{asset}', timeout=3) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn('javascript', response.headers['Content-Type'])
                if web_busy and (web_root / 'index.html').is_file():
                    self.assertIn('Local web port', (directory / 'logs' / 'backend.log').read_text(encoding='utf-8'))
                self.assertTrue((directory / 'BlockHouse.db').exists())
                until = time.monotonic() + 5
                while not list((directory / 'backups').glob('*.sqlite3')) and time.monotonic() < until: time.sleep(0.1)
                self.assertTrue(list((directory / 'backups').glob('*.sqlite3')))
                second = subprocess.run(command, cwd=folder, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                self.assertNotEqual(second.returncode, 0, 'Second process must not open the same database')
                # A different data folder must not allow a second BE to share the API port.
                other = directory / 'another-shop'
                other.mkdir()
                duplicate_command = [str(other) if value == folder else value for value in command]
                duplicate = subprocess.run(duplicate_command, cwd=other, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
                self.assertNotEqual(duplicate.returncode, 0)
                self.assertIn(str(port).encode(), duplicate.stderr)
                self.assertFalse((other / 'BlockHouse.db').exists())
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
                kernel.OpenEventW.restype = wintypes.HANDLE
                kernel.SetEvent.argtypes = [wintypes.HANDLE]
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = kernel.OpenEventW(0x0002, False, event)
                self.assertTrue(handle)
                try: self.assertTrue(kernel.SetEvent(handle))
                finally: kernel.CloseHandle(handle)
                exit_code = process.wait(timeout=35)
                log = directory / 'logs' / 'backend.log'
                self.assertEqual(exit_code, 0, log.read_text(encoding='utf-8')[-4000:] if log.exists() else 'No backend log')
                if (web_root / 'index.html').is_file() and not web_busy:
                    with self.assertRaises(urllib.error.URLError):
                        urllib.request.urlopen(f'http://127.0.0.1:{web_port}/', timeout=1)
                with closing(sqlite3.connect(directory / 'BlockHouse.db')) as db:
                    self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            finally:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)

if __name__ == '__main__': unittest.main()
