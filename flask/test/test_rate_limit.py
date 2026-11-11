import unittest

from rate_limit import RateLimiter, parse_rate
from test.app_fixture import load_app


class RateLimiterTestCase(unittest.TestCase):
    def test_parse_rate(self):
        self.assertEqual(parse_rate(None, '20/hour'), (20, 3600))
        self.assertEqual(parse_rate(' 5 / Minute ', '20/hour'), (5, 60))
        self.assertEqual(parse_rate('100/day', '20/hour'), (100, 86400))
        for off in ('0', 'off', 'false', 'none', ''):
            self.assertIsNone(parse_rate(off, '20/hour'))
        for invalid in ('20', 'many/hour', '20/week', '0/hour', '-1/hour'):
            with self.assertRaises(ValueError):
                parse_rate(invalid, '20/hour')

    def test_sliding_window_per_key(self):
        now = [1000.0]
        limiter = RateLimiter(2, 60, clock=lambda: now[0])
        self.assertIsNone(limiter.hit('a'))
        now[0] += 10
        self.assertIsNone(limiter.hit('a'))
        self.assertIsNone(limiter.hit('b'), 'each key has its own limit')
        self.assertEqual(limiter.hit('a'), 50, 'wait until the first hit leaves the window')
        now[0] += 50
        self.assertIsNone(limiter.hit('a'))
        self.assertEqual(limiter.hit('a'), 10)

    def test_old_keys_are_forgotten(self):
        now = [0.0]
        limiter = RateLimiter(1, 60, clock=lambda: now[0])
        limiter.MAX_KEYS = 3
        for key in 'abc':
            limiter.hit(key)
        now[0] += 61
        limiter.hit('d')
        self.assertEqual(list(limiter.hits), ['d'])


class CreateEndpointTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.flask_app = load_app()

    def setUp(self) -> None:
        self.http = self.flask_app.app.test_client()
        self.previous_limiter = self.flask_app.create_limiter

    def tearDown(self) -> None:
        self.flask_app.create_limiter = self.previous_limiter

    def create(self, body, ip='10.0.0.1'):
        return self.http.post('/create', json=body, environ_base={'REMOTE_ADDR': ip})

    def test_create_validates_the_game(self):
        self.flask_app.create_limiter = None
        response = self.create({'name': 'Team', 'deck': 'POWERS'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.flask_app.gm.get(response.get_data(as_text=True)).name, 'Team')
        for body in ({}, {'name': 'Team'}, {'name': '  ', 'deck': 'POWERS'}, {'name': 5, 'deck': 'POWERS'}, ['x']):
            self.assertEqual(self.create(body).status_code, 400, body)
        self.assertEqual(self.http.post('/create', data='nope', content_type='application/json').status_code, 400)
        response = self.create({'name': 'Team', 'deck': 'HOLDEM'})
        self.assertEqual((response.status_code, response.get_json()['code']), (400, 4001))

    def test_create_is_rate_limited_per_address(self):
        self.flask_app.create_limiter = RateLimiter(2, 3600)
        for _ in range(2):
            self.assertEqual(self.create({'name': 'Team', 'deck': 'FIBONACCI'}).status_code, 200)
        refused = self.create({'name': 'Team', 'deck': 'FIBONACCI'})
        self.assertEqual(refused.status_code, 429)
        self.assertGreater(int(refused.headers['Retry-After']), 0)
        self.assertEqual(self.create({'name': 'Team', 'deck': 'FIBONACCI'}, ip='10.0.0.2').status_code, 200)
        # invalid requests do not use up the limit
        self.flask_app.create_limiter = RateLimiter(1, 3600)
        self.create({'name': ''}, ip='10.0.0.3')
        self.assertEqual(self.create({'name': 'Team', 'deck': 'FIBONACCI'}, ip='10.0.0.3').status_code, 200)


    def test_large_bodies_are_refused(self):
        self.flask_app.create_limiter = None
        huge = {'name': 'x' * (600 * 1024), 'deck': 'FIBONACCI'}
        refused = self.create(huge)
        self.assertEqual((refused.status_code, refused.get_json()['error']), (413, 'Request too large: 512 KB at most'))
        mcp = self.http.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping', 'params': {'pad': 'x' * (600 * 1024)}})
        self.assertEqual(mcp.status_code, 413)
        # the largest backlog the server accepts still fits
        game_id = self.flask_app.gm.create('Big backlog')
        stories = [{'name': 'Історія ' * 12, 'ref': f'ABC-{i}', 'url': 'https://tracker.example.com/' + 'p' * 450}
                   for i in range(200)]
        response = self.http.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'add_to_backlog', 'arguments': {'room': game_id, 'stories': stories}}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()['result']['structuredContent']['added']), 200)


if __name__ == '__main__':
    unittest.main()
