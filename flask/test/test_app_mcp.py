import unittest

from test.app_fixture import load_app


class McpTestCase(unittest.TestCase):
    """The MCP server, used by the AI agents of the rooms whose players let them in"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.flask_app = load_app()

    def setUp(self) -> None:
        self.flask_app.mcp_enabled = True
        self.gm = self.flask_app.gm
        self.game_id = self.gm.create('Sprint 42')
        _, key = self.gm.enable_agent_access(self.game_id)
        self.link = f'http://localhost/game/{self.game_id}?agent={key}'
        self.http = self.flask_app.app.test_client()

    def tearDown(self) -> None:
        self.gm.games.pop(self.game_id, None)

    def rpc(self, method, params=None, message_id=1, url='/mcp', **kwargs):
        message = {'jsonrpc': '2.0', 'method': method}
        if message_id is not None:
            message['id'] = message_id
        if params is not None:
            message['params'] = params
        return self.http.post(url, json=message, **kwargs)

    def call(self, tool, room=None, **arguments):
        response = self.rpc('tools/call', {'name': tool, 'arguments': {'room': room or self.link, **arguments}})
        self.assertEqual(response.status_code, 200)
        return response.get_json()['result']

    def player(self, name, game_id=None):
        client = self.flask_app.socketio.test_client(self.flask_app.app)
        info = client.emit('join', {'game': game_id or self.game_id, 'name': name, 'spectator': False}, callback=True)
        return client, info

    def test_initialize_and_list_tools(self):
        response = self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                           'clientInfo': {'name': 'test', 'version': '1'}})
        result = response.get_json()['result']
        self.assertEqual(result['protocolVersion'], '2025-06-18')
        self.assertIn('tools', result['capabilities'])
        self.assertIn('agent link', result['instructions'])
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

    def test_agents_need_the_agent_link_of_a_room_that_lets_them_in(self):
        closed = self.gm.create('Closed')
        for room in (closed, f'http://localhost/game/{closed}?agent=guess', self.game_id,
                     f'http://localhost/game/{self.game_id}', f'http://localhost/game/{self.game_id}?agent=wrong'):
            result = self.call('list_backlog', room=room)
            self.assertTrue(result['isError'], room)
            self.assertIn('AI agents are not allowed in this room', result['content'][0]['text'])
        self.assertTrue(self.call('add_to_backlog', room=closed, stories=[{'name': 'x'}])['isError'])
        self.assertEqual(self.gm.get_for_stories(closed).get_backlog(), [])
        self.assertFalse(self.call('list_backlog')['isError'])
        result = self.rpc('tools/call', {'name': 'get_room', 'arguments': {}}).get_json()['result']
        self.assertTrue(result['isError'])

    def test_turning_off_revokes_the_link_and_turning_on_again_gives_a_new_one(self):
        key = self.link.split('agent=')[1]
        self.assertEqual(self.gm.enable_agent_access(self.game_id)[1], key, 'turning it on again keeps the link')
        self.gm.disable_agent_access(self.game_id)
        self.assertTrue(self.call('list_backlog')['isError'])
        _, new_key = self.gm.enable_agent_access(self.game_id)
        self.assertNotEqual(key, new_key)
        self.assertTrue(self.call('list_backlog')['isError'])
        self.assertFalse(self.call('list_backlog', room=f'http://x/game/{self.game_id}?agent={new_key}')['isError'])

    def test_tool_errors_are_reported_to_the_agent(self):
        result = self.call('update_story', id=99, name='x')
        self.assertTrue(result['isError'])
        self.assertIn('does not exist', result['content'][0]['text'])
        result = self.call('add_to_backlog', stories=[{'name': 'x', 'url': 'javascript:alert(1)'}])
        self.assertTrue(result['isError'])

    def test_an_agent_fills_the_backlog_and_reads_the_estimates(self):
        alice, info = self.player('Alice')
        self.assertTrue(info['agentAccess'])
        self.assertTrue(info['mcpAvailable'])
        bob, _ = self.player('Bob')
        alice.get_received()

        result = self.call('add_to_backlog', stories=[
            {'name': 'Login timeout', 'ref': 'ABC-1', 'url': 'https://tracker.example.com/ABC-1'},
            {'name': 'Export', 'ref': 'ABC-2'}])
        self.assertEqual(result['structuredContent']['added'], [1, 2])
        # the players see the backlog at once, and are told that an agent changed it
        received = alice.get_received()
        infos = [event['args'][0] for event in received if event['name'] == 'info']
        self.assertEqual(infos[-1]['current']['ref'], 'ABC-1')
        activities = [event['args'][0] for event in received if event['name'] == 'agent_activity']
        self.assertEqual(activities, [{'action': 'added', 'count': 2}])
        # sending the same issues again changes nothing, and tells nobody
        again = self.call('add_to_backlog', stories=[{'name': 'Export', 'ref': 'ABC-2'}])['structuredContent']
        self.assertEqual((again['added'], again['backlog_size']), ([], 2))
        self.assertEqual([e for e in alice.get_received() if e['name'] == 'agent_activity'], [])

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

        alice.get_received()
        self.assertFalse(self.call('update_story', id=1, estimate='5')['isError'])
        self.assertEqual([e['args'][0] for e in alice.get_received() if e['name'] == 'agent_activity'],
                         [{'action': 'updated', 'story': 'ABC-1 Login timeout'}])
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
        actions = [e['args'][0]['action'] for e in alice.get_received() if e['name'] == 'agent_activity']
        self.assertEqual(actions, ['requeued', 'moved', 'deleted', 'cleared'])
        alice.disconnect()
        bob.disconnect()

    def test_the_agent_link_can_be_in_the_url_of_the_server(self):
        key = self.link.split('agent=')[1]
        response = self.rpc('tools/call', {'name': 'list_backlog'}, url=f'/mcp?room={self.game_id}&agent={key}')
        self.assertFalse(response.get_json()['result']['isError'])
        response = self.rpc('tools/call', {'name': 'list_backlog'}, url=f'/mcp?room={self.game_id}')
        self.assertTrue(response.get_json()['result']['isError'])

    def test_t_shirt_estimates_use_their_labels(self):
        game_id = self.gm.create('Shirts', 'T_SHIRTS')
        _, key = self.gm.enable_agent_access(game_id)
        self.gm.join_game(game_id, 'p1', 'Alice', False)
        self.gm.pick_card(game_id, 'p1', 6)
        self.gm.reveal_cards(game_id)
        result = self.call('update_story', room=f'http://localhost/game/{game_id}?agent={key}', id=1, estimate='xxl')
        story = result['structuredContent']['story']
        self.assertEqual((story['estimate'], story['estimate_label'], story['votes'][0]['card']), (7, 'XXL', 'XL'))
        self.assertIsNone(self.call('list_stories', room=f'x/game/{game_id}?agent={key}')['structuredContent']['total'])
        self.gm.games.pop(game_id, None)

    def test_origin_and_switch(self):
        evil = {'Origin': 'https://evil.example.com'}
        self.assertEqual(self.rpc('ping', headers=evil).status_code, 403)
        self.assertEqual(self.rpc('ping', headers={'Origin': 'http://localhost'}).status_code, 200)
        self.flask_app.mcp_enabled = False
        self.assertEqual(self.rpc('ping').status_code, 404)
        self.assertEqual(self.http.get('/api/rooms/' + self.game_id).status_code, 200,
                         'there is no HTTP API anymore: the path is a page of the app')

    def test_players_turn_agent_access_on_and_off(self):
        game_id = self.gm.create('Players decide')
        alice, info = self.player('Alice', game_id)
        bob, _ = self.player('Bob', game_id)
        self.assertFalse(info['agentAccess'], 'agents are not let in by default')
        self.assertEqual(alice.emit('get_agent_link', callback=True), {'link': None})

        link = alice.emit('enable_agent_access', callback=True)['link']
        self.assertRegex(link, rf'^http://localhost/game/{game_id}\?agent=[A-Za-z0-9_-]{{32}}$')
        infos = [event['args'][0] for event in bob.get_received() if event['name'] == 'info']
        self.assertTrue(infos[-1]['agentAccess'], 'every player sees that agents are let in')
        # every player can show the link again, and turning it on again keeps it
        self.assertEqual(bob.emit('get_agent_link', callback=True), {'link': link})
        self.assertEqual(bob.emit('enable_agent_access', callback=True), {'link': link})
        self.assertFalse(self.call('list_backlog', room=link)['isError'])

        self.assertIsNone(bob.emit('renew_agent_link', callback=True), 'there is no way to replace a link that is on')

        bob.emit('disable_agent_access')
        infos = [event['args'][0] for event in alice.get_received() if event['name'] == 'info']
        self.assertFalse(infos[-1]['agentAccess'])
        self.assertTrue(self.call('list_backlog', room=link)['isError'])
        self.assertEqual(alice.emit('get_agent_link', callback=True), {'link': None})
        new_link = alice.emit('enable_agent_access', callback=True)['link']
        self.assertNotEqual(new_link, link)
        self.assertTrue(self.call('list_backlog', room=link)['isError'])
        self.assertFalse(self.call('list_backlog', room=new_link)['isError'])
        alice.emit('disable_agent_access')

        self.flask_app.mcp_enabled = False
        self.assertEqual(alice.emit('enable_agent_access', callback=True)['code'], 4010)
        _, info = self.player('Carol', game_id)
        self.assertFalse(info['mcpAvailable'])
        alice.disconnect()
        bob.disconnect()

    def test_agent_access_survives_restarts(self):
        from gamestate.game_manager import GameManager
        restarted = GameManager()
        self.assertTrue(restarted.get_for_stories(self.game_id).agent_access)
        restarted.authorize_agent(self.game_id, self.link.split('agent=')[1])

    def test_players_manage_the_backlog_through_the_socket(self):
        alice, _ = self.player('Alice')
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
