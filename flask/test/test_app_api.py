import unittest

from test.app_fixture import load_app


class AgentApiTestCase(unittest.TestCase):
    """The HTTP API and the MCP server used by AI agents"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.flask_app = load_app()

    def setUp(self) -> None:
        self.flask_app.api_enabled = True
        self.flask_app.api_token = None
        self.game_id = self.flask_app.gm.create('Sprint 42')
        self.http = self.flask_app.app.test_client()

    def tearDown(self) -> None:
        self.flask_app.gm.games.pop(self.game_id, None)

    def rpc(self, method, params=None, message_id=1, **kwargs):
        message = {'jsonrpc': '2.0', 'method': method}
        if message_id is not None:
            message['id'] = message_id
        if params is not None:
            message['params'] = params
        return self.http.post('/mcp', json=message, **kwargs)

    def call(self, tool, **arguments):
        response = self.rpc('tools/call', {'name': tool, 'arguments': {'room': self.game_id, **arguments}})
        self.assertEqual(response.status_code, 200)
        return response.get_json()['result']

    def player(self, name):
        client = self.flask_app.socketio.test_client(self.flask_app.app)
        client.emit('join', {'game': self.game_id, 'name': name, 'spectator': False})
        return client

    def test_initialize_and_list_tools(self):
        response = self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                           'clientInfo': {'name': 'test', 'version': '1'}})
        result = response.get_json()['result']
        self.assertEqual(result['protocolVersion'], '2025-06-18')
        self.assertIn('tools', result['capabilities'])
        self.assertEqual(self.rpc('initialize', {'protocolVersion': '1999-01-01'}).get_json()['result']['protocolVersion'],
                         '2025-11-25')
        self.assertEqual(self.rpc('notifications/initialized', message_id=None).status_code, 202)
        tools = {tool['name'] for tool in self.rpc('tools/list').get_json()['result']['tools']}
        self.assertTrue({'get_room', 'list_stories', 'add_to_backlog', 'export_stories'} <= tools)
        self.assertEqual(self.rpc('ping').get_json()['result'], {})

    def test_protocol_errors(self):
        self.assertEqual(self.rpc('nope').get_json()['error']['code'], -32601)
        self.assertEqual(self.rpc('tools/call', {'name': 'nope'}).get_json()['error']['code'], -32602)
        response = self.http.post('/mcp', data='{not json', content_type='application/json')
        self.assertEqual((response.status_code, response.get_json()['error']['code']), (400, -32700))
        self.assertEqual(self.http.post('/mcp', json=[1]).get_json()['error']['code'], -32600)
        self.assertEqual(self.http.get('/mcp').status_code, 405)

    def test_tool_errors_are_reported_to_the_agent(self):
        result = self.rpc('tools/call', {'name': 'get_room', 'arguments': {}}).get_json()['result']
        self.assertTrue(result['isError'])
        result = self.call('update_story', id=99, name='x')
        self.assertTrue(result['isError'])
        self.assertIn('does not exist', result['content'][0]['text'])
        result = self.call('add_to_backlog', stories=[{'name': 'x', 'url': 'javascript:alert(1)'}])
        self.assertTrue(result['isError'])

    def test_an_agent_fills_the_backlog_and_reads_the_estimates(self):
        alice = self.player('Alice')
        bob = self.player('Bob')
        alice.get_received()

        result = self.call('add_to_backlog', stories=[
            {'name': 'Login timeout', 'ref': 'ABC-1', 'url': 'https://tracker.example.com/ABC-1'},
            {'name': 'Export', 'ref': 'ABC-2'}])
        self.assertEqual(result['structuredContent']['added'], [1, 2])
        # the players see the backlog at once
        infos = [event['args'][0] for event in alice.get_received() if event['name'] == 'info']
        self.assertEqual(infos[-1]['current']['ref'], 'ABC-1')
        # sending the same issues again changes nothing
        again = self.call('add_to_backlog', stories=[{'name': 'Export', 'ref': 'ABC-2'}])['structuredContent']
        self.assertEqual((again['added'], again['backlog_size']), ([], 2))

        alice.emit('pick_card', {'card': 5})
        bob.emit('pick_card', {'card': 8})
        alice.emit('reveal_cards')

        stories = self.call('list_stories')['structuredContent']
        self.assertEqual(stories['total'], 8)
        story = stories['stories'][0]
        self.assertEqual((story['ref'], story['estimate'], story['agreement']), ('ABC-1', 8, 0.5))
        self.assertEqual(story['votes'], [{'player': 'Bob', 'card': '8'}, {'player': 'Alice', 'card': '5'}])
        self.assertEqual((story['lowest_vote'], story['highest_vote']), ('5', '8'))

        room = self.call('get_room')['structuredContent']
        self.assertEqual(room['link'], f'http://localhost/game/{self.game_id}')
        self.assertEqual(room['current_story']['ref'], 'ABC-1')
        self.assertEqual(sorted(player['name'] for player in room['players']), ['Alice', 'Bob'])

        self.assertFalse(self.call('update_story', id=1, estimate='5')['isError'])
        markdown = self.call('export_stories')['content'][0]['text']
        self.assertIn('| 1 | ABC-1 | Login timeout | 5 | Bob: 8, Alice: 5 | https://tracker.example.com/ABC-1 |',
                      markdown)
        csv = self.call('export_stories', format='csv')['content'][0]['text']
        self.assertTrue(csv.startswith('#,Ref,Story,Estimate,Votes,Link\n1,ABC-1,Login timeout,5,'))

        self.call('requeue_story', id=1)
        backlog = self.call('list_backlog')['structuredContent']['backlog']
        self.assertEqual([story['ref'] for story in backlog], ['ABC-1', 'ABC-2'])
        self.call('move_story', id=2, position=1)
        self.call('delete_story', id=1)
        self.assertEqual([s['ref'] for s in self.call('list_backlog')['structuredContent']['backlog']], ['ABC-2'])
        self.call('clear_backlog')
        self.assertEqual(self.call('list_backlog')['structuredContent']['backlog'], [])
        alice.disconnect()
        bob.disconnect()

    def test_the_room_can_be_given_by_its_link_or_in_the_url_of_the_server(self):
        link = f'https://poker.example.com/game/{self.game_id.upper()}'
        result = self.rpc('tools/call', {'name': 'get_room', 'arguments': {'room': link}}).get_json()['result']
        self.assertEqual(result['structuredContent']['room'], self.game_id)
        response = self.http.post(f'/mcp?room={self.game_id}',
                                  json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                                        'params': {'name': 'list_backlog'}})
        self.assertFalse(response.get_json()['result']['isError'])

    def test_t_shirt_estimates_use_their_labels(self):
        game_id = self.flask_app.gm.create('Shirts', 'T_SHIRTS')
        self.flask_app.gm.join_game(game_id, 'p1', 'Alice', False)
        self.flask_app.gm.pick_card(game_id, 'p1', 6)
        self.flask_app.gm.reveal_cards(game_id)
        result = self.rpc('tools/call', {'name': 'update_story',
                                         'arguments': {'room': game_id, 'id': 1, 'estimate': 'xxl'}}).get_json()
        story = result['result']['structuredContent']['story']
        self.assertEqual((story['estimate'], story['estimate_label'], story['votes'][0]['card']), (7, 'XXL', 'XL'))
        self.assertIsNone(self.http.get(f'/api/rooms/{game_id}').get_json()['total'])
        self.flask_app.gm.games.pop(game_id, None)

    def test_http_api(self):
        self.call('add_to_backlog', stories=[{'name': 'A | B', 'ref': 'ABC-1'}])
        data = self.http.get(f'/api/rooms/{self.game_id}').get_json()
        self.assertEqual((data['name'], data['backlog'][0]['ref'], data['stories']), ('Sprint 42', 'ABC-1', []))
        markdown = self.http.get(f'/api/rooms/{self.game_id}?format=markdown')
        self.assertEqual(markdown.mimetype, 'text/markdown')
        self.assertTrue(markdown.get_data(as_text=True).startswith('## Sprint 42'))
        self.assertEqual(self.http.get(f'/api/rooms/{self.game_id}?format=csv').mimetype, 'text/csv')
        self.assertEqual(self.http.get('/api/rooms/00000000-0000-0000-0000-000000000000').status_code, 404)
        self.assertEqual(self.http.get('/api/rooms/nope').status_code, 404)

    def test_token_origin_and_switch(self):
        self.flask_app.api_token = 's3cret'
        self.assertEqual(self.http.get(f'/api/rooms/{self.game_id}').status_code, 401)
        self.assertEqual(self.rpc('ping').status_code, 401)
        headers = {'Authorization': 'Bearer s3cret'}
        self.assertEqual(self.http.get(f'/api/rooms/{self.game_id}', headers=headers).status_code, 200)
        self.assertEqual(self.rpc('ping', headers=headers).status_code, 200)
        self.flask_app.api_token = None

        evil = {'Origin': 'https://evil.example.com'}
        self.assertEqual(self.rpc('ping', headers=evil).status_code, 403)
        self.assertEqual(self.rpc('ping', headers={'Origin': 'http://localhost'}).status_code, 200)

        self.flask_app.api_enabled = False
        self.assertEqual(self.rpc('ping').status_code, 404)
        self.assertEqual(self.http.get(f'/api/rooms/{self.game_id}').status_code, 404)

    def test_players_manage_the_backlog_through_the_socket(self):
        alice = self.player('Alice')
        alice.emit('add_to_backlog', {'stories': [{'name': 'A'}, {'name': 'B'}, {'name': 'C'}]})
        alice.emit('move_story', {'id': 3, 'position': 1})
        alice.emit('skip_story')
        infos = [event['args'][0] for event in alice.get_received() if event['name'] == 'info']
        self.assertEqual([story['name'] for story in infos[-1]['backlog']], ['A', 'B', 'C'])
        alice.emit('pick_card', {'card': 3})
        alice.emit('reveal_cards')
        alice.emit('requeue_story', {'id': 1})
        alice.emit('clear_backlog')
        error = alice.emit('add_to_backlog', {'stories': [{'name': ''}]}, callback=True)
        self.assertEqual(error['code'], 4009)
        info = [event['args'][0] for event in alice.get_received() if event['name'] == 'info'][-1]
        self.assertEqual((info['backlog'], info['history']), ([], []))
        alice.disconnect()


if __name__ == '__main__':
    unittest.main()
