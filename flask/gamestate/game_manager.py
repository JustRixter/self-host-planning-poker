import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from peewee import DoesNotExist, chunked

from gamestate.deck import Deck
from gamestate.exceptions import GameDoesNotExistError, DeckDoesNotExistError, GameNotOngoingError, \
    AgentAccessDeniedError
from gamestate.game import Game
from gamestate.models import StoredGame, StoredStory, RoomAgentAccess, database_proxy
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
        game = Game(stored_game.name, Deck[stored_game.deck], self.__load_stories(game_uuid))
        game.agent_access = RoomAgentAccess.select().where(RoomAgentAccess.game == str(game_uuid)).exists()
        return game

    def get_for_stories(self, game_uuid: str) -> Game:
        """The game, ongoing or not: the stories can be read and prepared before anybody joins.

        A game nobody plays is read from the database each time and not kept in memory.
        """
        return self.games.get(game_uuid) or self.__load(game_uuid)

    # AI agents: the players of a game let them in by turning on its agent access, which gives an agent link

    def enable_agent_access(self, game_uuid: str) -> tuple[dict, str]:
        """Lets AI agents in the game. Returns the info of the game and the key of its agent link (the existing one
        if agents were already let in)"""
        game = self.get_for_stories(game_uuid)
        key = self.get_agent_key(game_uuid)
        if key is None:
            key = secrets.token_urlsafe(24)
            RoomAgentAccess.create(game=str(game_uuid), key=key, created_at=self.__now())
        game.agent_access = True
        return game.info(), key

    def renew_agent_key(self, game_uuid: str) -> tuple[dict, str]:
        """Replaces the key of the agent link: the previous link stops working"""
        self.disable_agent_access(game_uuid)
        return self.enable_agent_access(game_uuid)

    def disable_agent_access(self, game_uuid: str) -> dict:
        game = self.get_for_stories(game_uuid)
        RoomAgentAccess.delete().where(RoomAgentAccess.game == str(game_uuid)).execute()
        game.agent_access = False
        return game.info()

    def get_agent_key(self, game_uuid: str) -> Optional[str]:
        access = RoomAgentAccess.get_or_none(RoomAgentAccess.game == str(game_uuid))
        return access.key if access else None

    def authorize_agent(self, game_uuid: str, key: Optional[str]) -> None:
        """Raises AgentAccessDeniedError unless the players let agents in the game and the key is the one of its link"""
        self.get_for_stories(game_uuid)  # raises if the game does not exist
        access = RoomAgentAccess.get_or_none(RoomAgentAccess.game == str(game_uuid))
        if access is None or not isinstance(key, str) or not hmac.compare_digest(access.key, key):
            raise AgentAccessDeniedError(
                'AI agents are not allowed in this room, or this agent link is not valid anymore. In the room, a player '
                'can turn on "AI agent access" and copy the agent link: https://<server>/game/<room>?agent=<key>')
        now = self.__now()
        if access.last_used_at is None or access.last_used_at < now - timedelta(minutes=1):
            RoomAgentAccess.update(last_used_at=now).where(RoomAgentAccess.game == str(game_uuid)).execute()

    @staticmethod
    def __now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

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
    