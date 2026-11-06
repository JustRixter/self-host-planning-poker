from collections import Counter
from typing import Optional, Union

from gamestate.deck import Deck
from gamestate.exceptions import PlayerNotInGameError, InvalidCardValueError, GameNotRevealedError, \
    StoryDoesNotExistError
from gamestate.player import Player

MAX_STORY_NAME_LENGTH = 100

# Values of Game.set_final_estimate() besides a card value
AUTO = 'auto'  # record the most-picked card
SKIP = 'skip'  # do not record anything for this turn


class Game:
    """Class representing the state of a game of Planning Poker"""
    def __init__(self, name: str, deck: Deck = Deck.FIBONACCI):
        self.name = name
        self.__state = {}
        self.__deck = deck
        self.__revealed = False
        self.__story = ''
        self.__final: Union[str, float] = AUTO
        # One entry per estimated story: {'name': str, 'estimate': number}
        self.__history: list[dict] = []

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

    def set_story_name(self, name: str) -> None:
        self.__story = self.__clean_story_name(name)

    @staticmethod
    def __clean_story_name(name: Optional[str]) -> str:
        return (name or '').strip()[:MAX_STORY_NAME_LENGTH]

    def update_story(self, index: int, name: Optional[str] = None, estimate: Optional[float] = None) -> None:
        """Edits the name and/or the estimate of an already estimated story"""
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(self.__history):
            raise StoryDoesNotExistError(f'Story {index} does not exist')
        if estimate is not None and estimate not in self.__deck.value:
            raise InvalidCardValueError(f'Card value {estimate} is not valid. Current deck is {self.__deck.name}')
        entry = self.__history[index]
        if name is not None:
            entry['name'] = self.__clean_story_name(name)
        if estimate is not None:
            entry['estimate'] = self.__number(estimate)

    def get_story_name(self) -> str:
        return self.__story

    def set_final_estimate(self, estimate: Union[str, float]) -> None:
        """Overrides what is recorded when the turn ends: AUTO, SKIP or a card of the current deck"""
        if not self.__revealed:
            raise GameNotRevealedError('The cards must be revealed before choosing the final estimate')
        if estimate not in (AUTO, SKIP) and estimate not in self.__deck.value:
            raise InvalidCardValueError(f'Card value {estimate} is not valid. Current deck is {self.__deck.name}')
        self.__final = estimate

    def end_turn(self) -> None:
        """Ends the turn, recording the story's estimate if the cards were revealed"""
        if self.__revealed:
            estimate = self.__estimate_to_record()
            if estimate is not None:
                self.__history.append({'name': self.__story, 'estimate': self.__number(estimate)})
        self.__reset_turn()

    def __reset_turn(self) -> None:
        self.__revealed = False
        self.__story = ''
        self.__final = AUTO
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

    def __estimate_to_record(self) -> Optional[float]:
        if self.__final == SKIP:
            return None
        if self.__final == AUTO:
            return self.__consensus_estimate()
        return self.__final

    @staticmethod
    def __number(card: float) -> Union[int, float]:
        return int(card) if float(card).is_integer() else card

    def get_history(self) -> list[dict]:
        return [dict(entry) for entry in self.__history]

    def get_estimates(self) -> dict:
        """Number of stories estimated per card value, ordered by card value"""
        counts = Counter(entry['estimate'] for entry in self.__history)
        return {str(card): count for card, count in sorted(counts.items())}

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
        """Return the players' with their hands"""
        self.__revealed = True

    def info(self) -> dict:
        recorded = self.__estimate_to_record() if self.__revealed else None
        mode = self.__final if self.__final in (AUTO, SKIP) else 'value'
        return {
            'name': self.name,
            'deck': self.__deck.name,
            'revealed': self.__revealed,
            'story': self.__story,
            'estimates': self.get_estimates(),
            'history': self.get_history(),
            'total': self.get_total(),
            'finalEstimate': {
                'mode': mode,
                'value': None if recorded is None else self.__number(recorded)
            }
        }
