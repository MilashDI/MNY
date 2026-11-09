import importlib.util
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('mny_server', Path(__file__).resolve().parents[1] / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class DatabaseTests(unittest.TestCase):
    def test_persistence_restart_conflicts_and_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            server.DATABASE = Path(directory) / 'mny.sqlite3'
            payload = {'players': [{'id': 'test-id', 'name': 'Ник', 'fullName': 'Имя', 'photo': 'data:image/jpeg;base64,dGVzdA=='}], 'games': [], 'active': None}
            def start():
                http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                threading.Thread(target=http.serve_forever, daemon=True).start()
                return http, f'http://127.0.0.1:{http.server_port}'
            def request(base, path='/api/state', value=None):
                req = Request(base+path, data=json.dumps(value).encode() if value is not None else None, method='PUT' if value is not None else 'GET', headers={'Content-Type': 'application/json'})
                with urlopen(req) as response:
                    return json.load(response)
            http, base = start()
            try:
                self.assertIsNone(request(base)['state'])
                self.assertEqual(request(base, value={'revision': 0, 'state': payload})['revision'], 1)
                with self.assertRaises(HTTPError) as error:
                    request(base, value={'revision': 0, 'state': payload})
                self.assertEqual(error.exception.code, 409)
            finally:
                http.shutdown(); http.server_close()
            http, base = start()
            try:
                self.assertEqual(request(base)['state'], payload)
                request(base, value={'revision': 1, 'state': payload})
                self.assertTrue(list((Path(directory)/'backups').glob('*.sqlite3')))
                with sqlite3.connect(server.DATABASE) as connection:
                    self.assertEqual(connection.execute('SELECT nickname,full_name,photo FROM players').fetchone(), ('Ник', 'Имя', payload['players'][0]['photo']))
                for path in ('/data/mny.sqlite3', '/%2e%2e/data/mny.sqlite3', '/server.py'):
                    with self.assertRaises(HTTPError) as error:
                        request(base, path)
                    self.assertEqual(error.exception.code, 404)
            finally:
                http.shutdown(); http.server_close()

if __name__ == '__main__':
    unittest.main()
