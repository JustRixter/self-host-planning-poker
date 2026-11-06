from collections import Counter
from typing import Optional

from gamestate.deck import Deck
from gamestate.exceptions import PlayerNotInGameError, InvalidCardValueError
from gamestate.player import Player


class Game:
    """Class representing the state of a game of Planning Poker"""
    def __init__(self, name: str, deck: Deck = Deck.FIBONACCI):
        self.name = name
        self.__state = {}
        self.__deck = deck
        self.__revealed = False
        self.__estimates: Counter = Counter()

    def player_joins(self, uuid: str, player: Player):
        self.__state[uuid] = player

    def player_leaves(self, uuid: str):
        self.__state.pop(uuid)

    def set_deck(self, deck: Deck):
        existing_deck = self.__deck
        self.__deck = deck
        if existing_deck is not deck:
            # Estimates from another deck are not comparable, so start over
            self.__estimates.clear()
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

    def end_turn(self) -> None:
        """Ends the turn, recording the story's estimate if the cards were revealed"""
        if self.__revealed:
            estimate = self.__consensus_estimate()
            if estimate is not None:
                self.__estimates[estimate] += 1
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

    def get_estimates(self) -> dict:
        """Number of stories estimated per card value, ordered by card value"""
        return {self.__format_card(card): count for card, count in sorted(self.__estimates.items())}

    @staticmethod
    def __format_card(card) -> str:
        return str(int(card)) if float(card).is_integer() else str(card)

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
        return {
            'name': self.name,
            'deck': self.__deck.name,
            'revealed': self.__revealed,
            'estimates': self.get_estimates()
        }
