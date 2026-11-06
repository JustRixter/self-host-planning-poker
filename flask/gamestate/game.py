from collections import Counter
from typing import Optional, Union

from gamestate.deck import Deck
from gamestate.exceptions import PlayerNotInGameError, InvalidCardValueError, StoryDoesNotExistError
from gamestate.player import Player

MAX_STORY_NAME_LENGTH = 100


class Game:
    """Class representing the state of a game of Planning Poker"""
    def __init__(self, name: str, deck: Deck = Deck.FIBONACCI):
        self.name = name
        self.__state = {}
        self.__deck = deck
        self.__revealed = False
        # One entry per revealed turn: {'id': int, 'name': str, 'estimate': number}
        self.__history: list[dict] = []
        self.__next_story_id = 1

    def player_joins(self, uuid: str, player: Player):
        self.__state[uuid] = player

    def player_leaves(self, uuid: str):
        self.__state.pop(uuid)

    def set_deck(self, deck: Deck):
        existing_deck = self.__deck
        self.__deck = deck
        if existing_deck is not deck:
            # Estimates from another deck are not comparable, so start over
            self.__history.clear()
            self.__reset_turn()

    def get_deck(self) -> Deck:
        return self.__deck

    def get_revealed(self) -> bool:
        return self.__revealed

    def list_players(self) -> [tuple[str, Player]]:
        return list(self.__state.items())

    def list_players_uuid(self) -> [str]:
        return list(self.__state)

    def get_player(self, uuid: str) -> Player:
        if uuid not in self.__state.keys():
            raise PlayerNotInGameError(f'Player with UUID {uuid} is not in this game')
        return self.__state.get(uuid)

    def player_picks(self, uuid: str, card: Optional[int]):
        if card is not None and card not in self.__deck.value:
            raise InvalidCardValueError(f'Card value {card} is not valid. Current deck is {self.__deck.name}')
        player: Player = self.get_player(uuid)
        player.set_hand(card)

    def update_story(self, story_id: int, name: Optional[str] = None, estimate: Optional[float] = None) -> None:
        """Edits the name and/or the estimate of an estimated story"""
        entry = self.__get_story(story_id)
        if estimate is not None and estimate not in self.__deck.value:
            raise InvalidCardValueError(f'Card value {estimate} is not valid. Current deck is {self.__deck.name}')
        if name is not None:
            entry['name'] = (name or '').strip()[:MAX_STORY_NAME_LENGTH]
        if estimate is not None:
            entry['estimate'] = self.__number(estimate)

    def delete_story(self, story_id: int) -> None:
        self.__history.remove(self.__get_story(story_id))

    def __get_story(self, story_id: int) -> dict:
        for entry in self.__history:
            if entry['id'] == story_id and not isinstance(story_id, bool):
                return entry
        raise StoryDoesNotExistError(f'Story {story_id} does not exist')

    def end_turn(self) -> None:
        self.__reset_turn()

    def __reset_turn(self) -> None:
        self.__revealed = False
        for player in self.__state.values():
            player.clear_hand()

    def __consensus_estimate(self) -> Optional[float]:
        """Most picked card; on a tie, the highest value wins. None if nobody picked a card."""
        hands = [p.get_hand() for p in self.get_non_spectator_players() if p.has_picked_card()]
        if not hands:
            return None
        counts = Counter(hands)
        top = max(counts.values())
        return max(card for card, count in counts.items() if count == top)

    @staticmethod
    def __number(card: float) -> Union[int, float]:
        return int(card) if float(card).is_integer() else card

    def get_history(self) -> list[dict]:
        return [dict(entry) for entry in self.__history]

    def get_total(self) -> Union[int, float]:
        """Sum of the estimates of all the stories"""
        total = sum(entry['estimate'] for entry in self.__history)
        return round(total, 2)

    def is_game_empty(self) -> bool:
        return len(self.__state) == 0

    def has_all_players_picked_card(self) -> bool:
        non_spectators = self.get_non_spectator_players()
        players_that_played_count = sum(1 for p in non_spectators if p.has_picked_card())
        return players_that_played_count == len(non_spectators)

    def get_non_spectator_players(self) -> [Player]:
        return list(filter(lambda p: p.spectator is False, self.__state.values()))

    def state(self) -> dict:
        """Returns the game's state with the players' hands hidden or shown depending on revealed's value"""
        return dict(list(map(
            lambda i: (i[0], i[1].state_with_hand() if self.__revealed else i[1].state()),
            self.list_players()
        )))

    def reveal_hands(self) -> None:
        """Shows the players' hands and records the turn's estimate (the most-picked card) in the history"""
        if self.__revealed:
            return
        self.__revealed = True
        estimate = self.__consensus_estimate()
        if estimate is not None:
            self.__history.append({'id': self.__next_story_id, 'name': '', 'estimate': self.__number(estimate)})
            self.__next_story_id += 1

    def info(self) -> dict:
        return {
            'name': self.name,
            'deck': self.__deck.name,
            'revealed': self.__revealed,
            'history': self.get_history(),
            'total': self.get_total()
        }
