import json
import uuid
from typing import Optional

from peewee import DoesNotExist, chunked

from gamestate.deck import Deck
from gamestate.exceptions import GameDoesNotExistError, DeckDoesNotExistError, GameNotOngoingError
from gamestate.game import Game
from gamestate.models import StoredGame, StoredStory, database_proxy
from gamestate.player import Player


class GameManager:
    """Class that manages games"""
    def __init__(self):
        self.games = {}

    def create(self, name: str, deck_name='FIBONACCI') -> str:
        game_uuid = str(uuid.uuid4())
        deck = self.__get_deck(deck_name)
        StoredGame.create(uuid=game_uuid, name=name, deck=deck_name)
        self.games[game_uuid] = Game(name, deck)
        return game_uuid

    def get(self, game_uuid: str) -> Game:
        game = self.games.get(game_uuid)
        if game is None:
            game = self.__load(game_uuid)
            self.games[game_uuid] = game
        return game

    def __load(self, game_uuid: str) -> Game:
        try:
            uuid.UUID(str(game_uuid))
            stored_game = StoredGame.get(StoredGame.uuid == game_uuid)
        except (ValueError, DoesNotExist):
            raise GameDoesNotExistError(f'Game {game_uuid} does not exist')
        return Game(stored_game.name, Deck[stored_game.deck], self.__load_stories(game_uuid))

    def get_for_stories(self, game_uuid: str) -> Game:
        """The game, ongoing or not: the stories can be read and prepared before anybody joins.

        A game nobody plays is read from the database each time and not kept in memory.
        """
        return self.games.get(game_uuid) or self.__load(game_uuid)

    @staticmethod
    def __load_stories(game_uuid: str) -> list[dict]:
        query = StoredStory.select().where(StoredStory.game == str(game_uuid)).order_by(StoredStory.position)
        return [{
            'id': row.story_id,
            'status': row.status,
            'name': row.name,
            'ref': row.ref,
            'url': row.url,
            'estimate': row.estimate,
            'votes': json.loads(row.votes) if row.votes else [],
        } for row in query]

    @staticmethod
    def __save_stories(game_uuid: str, game: Game) -> None:
        rows = [{
            'game': str(game_uuid),
            'story_id': story['id'],
            'status': story['status'],
            'position': position,
            'name': story['name'],
            'ref': story['ref'],
            'url': story['url'],
            'estimate': story.get('estimate'),
            'votes': json.dumps(story['votes']) if 'votes' in story else None,
        } for position, story in enumerate(game.stories())]
        with database_proxy.atomic():
            StoredStory.delete().where(StoredStory.game == str(game_uuid)).execute()
            for batch in chunked(rows, 50):
                StoredStory.insert_many(batch).execute()

    def __get_ongoing_game(self, game_uuid: str) -> Game:
        game = self.games.get(game_uuid)
        if game is None:
            raise GameNotOngoingError(f'Game {game_uuid} is not ongoing')
        return game
    
    def set_deck(self, game_uuid: str, deck_name: str) -> tuple[dict, dict]:
        deck = self.__get_deck(deck_name)
        game = self.__get_ongoing_game(game_uuid)
        game.set_deck(deck)
        self.__save_stories(game_uuid, game)
        StoredGame.update(deck=deck_name).where(StoredGame.uuid == uuid.UUID(game_uuid)).execute()
        return game.info(), game.state()

    def join_game(self, game_uuid: str, player_id: str, player_name: str, is_spectator: bool) -> tuple[dict, dict]:
        game = self.get(game_uuid)
        player = Player(player_name, is_spectator)
        game.player_joins(player_id, player)
        return game.info(), game.state()

    def leave_game(self, game_uuid: str, player_uuid: str) -> dict:
        game = self.__get_ongoing_game(game_uuid)
        game.player_leaves(player_uuid)
        if game.is_game_empty():
            self.games.pop(game_uuid)
        return game.state()

    def rename_game(self, game_uuid: str, game_name: str) -> dict:
        game = self.__get_ongoing_game(game_uuid)
        game.name = game_name
        StoredGame.update(name=game_name).where(StoredGame.uuid == uuid.UUID(game_uuid)).execute()
        return game.info()

    def set_player_name(self, game_uuid: str, player_uuid: str, player_name: str) -> dict:
        game = self.__get_ongoing_game(game_uuid)
        player = game.get_player(player_uuid)
        player.name = player_name
        return game.state()

    def set_player_spectator(self, game_uuid: str, player_uuid: str, is_spectator: bool) -> dict:
        game = self.__get_ongoing_game(game_uuid)
        player = game.get_player(player_uuid)
        player.spectator = is_spectator
        player.clear_hand()
        return game.state()

    def pick_card(self, game_uuid: str, player_uuid: str, pick: Optional[int]) -> dict:
        game = self.__get_ongoing_game(game_uuid)
        game.player_picks(player_uuid, pick)
        return game.state()

    def update_story(self, game_uuid: str, story_id: int, name=None, estimate=None) -> dict:
        game = self.get_for_stories(game_uuid)
        game.update_story(story_id, name, estimate)
        self.__save_stories(game_uuid, game)
        return game.info()

    def delete_story(self, game_uuid: str, story_id: int) -> dict:
        game = self.get_for_stories(game_uuid)
        game.delete_story(story_id)
        self.__save_stories(game_uuid, game)
        return game.info()

    def add_to_backlog(self, game_uuid: str, stories: list[dict]) -> tuple[dict, dict]:
        """Returns the info of the game and what was added or skipped"""
        game = self.get_for_stories(game_uuid)
        result = game.add_to_backlog(stories)
        self.__save_stories(game_uuid, game)
        return game.info(), result

    def move_story(self, game_uuid: str, story_id: int, position: int) -> dict:
        game = self.get_for_stories(game_uuid)
        game.move_story(story_id, position)
        self.__save_stories(game_uuid, game)
        return game.info()

    def skip_story(self, game_uuid: str) -> dict:
        game = self.get_for_stories(game_uuid)
        game.skip_story()
        self.__save_stories(game_uuid, game)
        return game.info()

    def requeue_story(self, game_uuid: str, story_id: int) -> dict:
        game = self.get_for_stories(game_uuid)
        game.requeue_story(story_id)
        self.__save_stories(game_uuid, game)
        return game.info()

    def clear_backlog(self, game_uuid: str) -> dict:
        game = self.get_for_stories(game_uuid)
        game.clear_backlog()
        self.__save_stories(game_uuid, game)
        return game.info()

    def reveal_cards(self, game_uuid: str) -> tuple[dict, dict]:
        game = self.__get_ongoing_game(game_uuid)
        game.reveal_hands()
        self.__save_stories(game_uuid, game)
        return game.state(), game.info()

    def end_turn(self, game_uuid: str) -> tuple[dict, dict]:
        game = self.__get_ongoing_game(game_uuid)
        game.end_turn()
        return game.state(), game.info()

    @staticmethod
    def __get_deck(deck_name) -> Deck:
        if deck_name not in Deck.__members__.keys():
            raise DeckDoesNotExistError(f'Deck {deck_name} does not exist')
        deck = Deck[deck_name]
        return deck
    