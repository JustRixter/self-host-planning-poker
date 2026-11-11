import unittest

from test.app_fixture import load_app


class DisconnectTestCase(unittest.TestCase):
    """The players who leave must be removed from the game and the others must be told"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.flask_app = load_app()

    def setUp(self) -> None:
        self.game_id = self.flask_app.gm.create('Disconnect test')

    def connect(self, name):
        client = self.flask_app.socketio.test_client(self.flask_app.app)
        client.emit('join', {'game': self.game_id, 'name': name, 'spectator': False})
        return client

    def players(self):
        return sorted(player.name for _, player in self.flask_app.gm.get(self.game_id).list_players())

    def test_a_player_who_leaves_is_removed_and_the_others_are_told(self):
        alice = self.connect('Alice')
        bob = self.connect('Bob')
        self.assertEqual(self.players(), ['Alice', 'Bob'])
        alice.get_received()

        bob.disconnect()

        self.assertEqual(self.players(), ['Alice'])
        states = [event for event in alice.get_received() if event['name'] == 'state']
        self.assertEqual([player['name'] for player in states[-1]['args'][0].values()], ['Alice'])

    def test_a_client_that_never_joined_does_not_break_anything(self):
        alice = self.connect('Alice')
        stranger = self.flask_app.socketio.test_client(self.flask_app.app)
        stranger.disconnect()
        self.assertEqual(self.players(), ['Alice'])
        self.assertTrue(alice.is_connected())


if __name__ == '__main__':
    unittest.main()
