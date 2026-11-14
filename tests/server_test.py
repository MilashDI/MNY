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
    def test_broadcast_events_preserve_phase_order_and_repeat_checks(self):
        game = {'day': 1, 'phase': 'night', 'seats': [{'alive': False, 'reason': 'Заголосован'}, {'alive': True}], 'nights': [{'day': 0, 'kill': 1, 'don': 0, 'sheriff': 1}], 'nightDraft': {'missed': True, 'don': 0, 'sheriff': 1}, 'phaseHistory': [{'state': {'day': 0, 'seats': [{'alive': False, 'reason': 'Заголосован'}]}}], 'phaseCursor': 0}
        events = server.broadcast_events(game)
        self.assertEqual([e['kind'] for e in events], ['vote', 'shot', 'don', 'sheriff', 'vote', 'don', 'sheriff'])
        self.assertEqual(events[0]['number'], 1)
        game['nightDraft']['don'] = 1
        self.assertEqual(server.broadcast_events(game)[-2]['number'], 2)
        game['seats'][0]['alive'] = True
        self.assertTrue(all(e['number'] == 0 for e in server.broadcast_events(game) if e['kind'] == 'vote'))

    def test_removals_appear_on_the_assigned_voting_day_only(self):
        game = {'day': 0, 'phase': 'day', 'seats': [{'alive': False, 'reason': 'Удалён днём'}, {'alive': False, 'reason': 'Удалён днём'}], 'voteDisqualifications': [{'seat': 0, 'targets': [0]}, {'seat': 1, 'targets': [1]}], 'nights': []}
        votes = lambda: [(event['day'], event['number']) for event in server.broadcast_events(game) if event['kind'] == 'vote']
        self.assertEqual(votes(), [(0, 1)])
        game['day'] = 1
        game['nights'] = [{'day': 0}]
        self.assertEqual(votes(), [(0, 1), (1, 2)])
        game['seats'][0]['alive'] = True
        game['voteDisqualifications'] = [{'seat': 1, 'targets': [0]}]
        self.assertEqual(votes(), [(0, 2)])
        game['voteDisqualifications'] = [{'seat': 1, 'targets': [2]}]
        game['seats'][1]['reason'] = 'Удалён ночью'
        self.assertEqual(votes(), [(0, 0)])
        game['day'] = 2
        self.assertEqual(votes(), [(0, 0), (2, 2)])
        game['voteDisqualifications'].append({'seat': 1, 'targets': [2]})
        self.assertEqual(votes(), [(0, 0), (2, 2)])

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
                broadcast_state = dict(payload, active={'id': 'game', 'phase': 'day', 'guests': {'guest': 'Гость'}, 'seats': [{'id': 'test-id', 'role': 'sheriff', 'roleAssigned': True, 'alive': True}, {'id': 'guest', 'role': 'civil', 'roleAssigned': False, 'alive': False}]})
                request(base, value={'revision': 1, 'state': broadcast_state})
                overlay = request(base, '/api/broadcast')
                self.assertEqual(overlay['gameId'], 'game')
                self.assertEqual(overlay['seats'][0]['name'], 'Ник')
                self.assertEqual(overlay['seats'][0]['role'], 'sheriff')
                self.assertEqual(overlay['seats'][1]['name'], 'Гость')
                self.assertIsNone(overlay['seats'][1]['role'])
                self.assertFalse(overlay['seats'][1]['alive'])
                self.assertNotIn('fullName', overlay['seats'][0])
                self.assertNotIn('data:image', json.dumps(overlay))
                with urlopen(base + overlay['seats'][0]['photo']) as image:
                    self.assertEqual(image.read(), b'test')
                    self.assertEqual(image.headers['Content-Type'], 'image/jpeg')
                request(base, value={'revision': 2, 'state': payload})
                self.assertEqual(request(base)['state'], payload)
                request(base, value={'revision': 3, 'state': payload})
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
