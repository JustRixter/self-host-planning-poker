import copy
from collections import Counter
from typing import Optional, Union
from urllib.parse import urlparse

from gamestate.deck import Deck
from gamestate.exceptions import PlayerNotInGameError, InvalidCardValueError, StoryDoesNotExistError, \
    InvalidStoryError
from gamestate.player import Player

MAX_STORY_NAME_LENGTH = 100
MAX_REF_LENGTH = 50
MAX_URL_LENGTH = 500
MAX_BACKLOG_SIZE = 200

QUEUED = 'queued'
ESTIMATED = 'estimated'


class Game:
    """Class representing the state of a game of Planning Poker

    Stories are either waiting in the backlog (the first one is estimated next) or estimated (the history).
    Each story is a dict: {'id': int, 'name': str, 'ref': str|None, 'url': str|None}, and estimated stories
    also have 'estimate': number and 'votes': [{'player': str, 'card': number}].
    """
    def __init__(self, name: str, deck: Deck = Deck.FIBONACCI, stories: Optional[list[dict]] = None):
        self.name = name
        self.__state = {}
        self.__deck = deck
        self.__revealed = False
        self.__history: list[dict] = []
        self.__backlog: list[dict] = []
        # The story estimated by the revealed turn, shown as the current one until the next turn
        self.__turn_story_id: Optional[int] = None
        self.__next_story_id = 1
        for story in stories or []:
            self.__restore(story)

    def __restore(self, story: dict) -> None:
        entry = {
            'id': story['id'],
            'name': story.get('name') or '',
            'ref': story.get('ref'),
            'url': story.get('url'),
        }
        if story['status'] == ESTIMATED:
            entry['estimate'] = self.__number(story['estimate'])
            entry['votes'] = list(story.get('votes') or [])
            self.__history.append(entry)
        else:
            self.__backlog.append(entry)
        self.__next_story_id = max(self.__next_story_id, entry['id'] + 1)

    def player_joins(self, uuid: str, player: Player):
        self.__state[uuid] = player

    def player_leaves(self, uuid: str):
        self.__state.pop(uuid)

    def set_deck(self, deck: Deck):
        existing_deck = self.__deck
        self.__deck = deck
        if existing_deck is not deck:
            # Estimates from another deck are not comparable, so start over. The backlog is not estimated yet: keep it
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

    # Stories

    def update_story(self, story_id: int, name: Optional[str] = None, estimate: Optional[float] = None) -> None:
        """Edits the name of a story and/or the estimate of an estimated story"""
        entry = self.__get_story(story_id)
        if estimate is not None:
            if 'estimate' not in entry:
                raise InvalidStoryError(f'Story {story_id} is not estimated yet')
            if estimate not in self.__deck.value or isinstance(estimate, bool):
                raise InvalidCardValueError(f'Card value {estimate} is not valid. Current deck is {self.__deck.name}')
        if name is not None:
            entry['name'] = self.__clean_name(name)
        if estimate is not None:
            entry['estimate'] = self.__number(estimate)

    def delete_story(self, story_id: int) -> None:
        entry = self.__get_story(story_id)
        if entry in self.__history:
            self.__history.remove(entry)
        else:
            self.__backlog.remove(entry)
        if self.__turn_story_id == story_id:
            self.__turn_story_id = None

    def add_to_backlog(self, stories: list[dict]) -> dict:
        """Adds stories at the end of the backlog: [{'name': str, 'ref'?: str, 'url'?: str}].

        A story whose ref is already in the game (in the backlog or estimated) is skipped, and so are the ones that
        do not fit in the backlog anymore. Nothing is added if one of the stories is invalid.
        Returns {'added': [ids], 'skipped': [{'name', 'ref', 'reason'}]}.
        """
        if not isinstance(stories, list):
            raise InvalidStoryError('Stories must be a list')
        cleaned = [self.__clean_new_story(story) for story in stories]

        known_refs = {entry['ref'].lower() for entry in self.__history + self.__backlog if entry['ref']}
        added, skipped = [], []
        for story in cleaned:
            ref_key = story['ref'].lower() if story['ref'] else None
            if ref_key and ref_key in known_refs:
                skipped.append({'name': story['name'], 'ref': story['ref'], 'reason': 'already in this room'})
            elif len(self.__backlog) >= MAX_BACKLOG_SIZE:
                skipped.append({'name': story['name'], 'ref': story['ref'],
                                'reason': f'the backlog is full ({MAX_BACKLOG_SIZE} stories)'})
            else:
                story['id'] = self.__next_story_id
                self.__next_story_id += 1
                self.__backlog.append(story)
                added.append(story['id'])
                if ref_key:
                    known_refs.add(ref_key)
        return {'added': added, 'skipped': skipped}

    def move_story(self, story_id: int, position: int) -> None:
        """Moves a story of the backlog to a position, starting at 1 (the next story to estimate)"""
        entry = self.__get_backlog_story(story_id)
        if not isinstance(position, int) or isinstance(position, bool):
            raise InvalidStoryError(f'Position {position} is not a number')
        self.__backlog.remove(entry)
        index = min(max(position, 1), len(self.__backlog) + 1) - 1
        self.__backlog.insert(index, entry)

    def skip_story(self) -> None:
        """Sends the next story of the backlog to the end of it, to estimate it later"""
        if self.__backlog:
            self.__backlog.append(self.__backlog.pop(0))

    def requeue_story(self, story_id: int) -> None:
        """Puts an estimated story back at the top of the backlog to vote on it again"""
        entry = self.__get_story(story_id)
        if entry not in self.__history:
            raise InvalidStoryError(f'Story {story_id} is not estimated yet')
        self.__history.remove(entry)
        if self.__turn_story_id == story_id:
            self.__turn_story_id = None
        self.__backlog.insert(0, {'id': entry['id'], 'name': entry['name'], 'ref': entry['ref'], 'url': entry['url']})

    def clear_backlog(self) -> None:
        self.__backlog.clear()

    def __get_story(self, story_id: int) -> dict:
        if not isinstance(story_id, bool):
            for entry in self.__history + self.__backlog:
                if entry['id'] == story_id:
                    return entry
        raise StoryDoesNotExistError(f'Story {story_id} does not exist')

    def __get_backlog_story(self, story_id: int) -> dict:
        entry = self.__get_story(story_id)
        if entry not in self.__backlog:
            raise InvalidStoryError(f'Story {story_id} is not in the backlog')
        return entry

    @staticmethod
    def __clean_name(name) -> str:
        if not isinstance(name, str):
            raise InvalidStoryError('The name of a story must be a text')
        return ' '.join(name.split())[:MAX_STORY_NAME_LENGTH]

    @classmethod
    def __clean_new_story(cls, story) -> dict:
        if not isinstance(story, dict):
            raise InvalidStoryError('A story must be an object with a name')
        name = cls.__clean_name(story.get('name') or '')
        ref = story.get('ref')
        if ref is not None and not isinstance(ref, str):
            raise InvalidStoryError('The ref of a story must be a text')
        ref = ' '.join((ref or '').split())[:MAX_REF_LENGTH] or None
        if not name and not ref:
            raise InvalidStoryError('A story needs a name or a ref')
        return {'id': None, 'name': name, 'ref': ref, 'url': cls.__clean_url(story.get('url'))}

    @staticmethod
    def __clean_url(url) -> Optional[str]:
        if url is None or url == '':
            return None
        if not isinstance(url, str):
            raise InvalidStoryError('The url of a story must be a text')
        url = url.strip()
        parsed = urlparse(url)
        # Shown as a link to every player: only web links, never javascript: or data: ones
        if len(url) > MAX_URL_LENGTH or parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise InvalidStoryError(f'{url[:MAX_URL_LENGTH]} is not a valid http(s) link')
        return url

    # Turns

    def end_turn(self) -> None:
        self.__reset_turn()

    def __reset_turn(self) -> None:
        self.__revealed = False
        self.__turn_story_id = None
        for player in self.__state.values():
            player.clear_hand()

    def __votes(self) -> list[dict]:
        votes = [{'player': p.name, 'card': self.__number(p.get_hand())}
                 for p in self.get_non_spectator_players() if p.has_picked_card()]
        return sorted(votes, key=lambda vote: (-vote['card'], vote['player'].lower()))

    @staticmethod
    def consensus(cards: list) -> Optional[float]:
        """Most picked card; on a tie, the highest value wins. None if nobody picked a card."""
        if not cards:
            return None
        counts = Counter(cards)
        top = max(counts.values())
        return max(card for card, count in counts.items() if count == top)

    @staticmethod
    def __number(card: float) -> Union[int, float]:
        return int(card) if float(card).is_integer() else card

    def get_history(self) -> list[dict]:
        return copy.deepcopy(self.__history)

    def get_backlog(self) -> list[dict]:
        return copy.deepcopy(self.__backlog)

    def get_current_story(self) -> Optional[dict]:
        """The story being estimated: the one estimated by the revealed turn, otherwise the next one of the backlog"""
        if self.__turn_story_id is not None:
            for entry in self.__history:
                if entry['id'] == self.__turn_story_id:
                    return copy.deepcopy(entry)
        return copy.deepcopy(self.__backlog[0]) if self.__backlog else None

    def stories(self) -> list[dict]:
        """All the stories with their status, in order, to store them"""
        return [{**entry, 'status': QUEUED} for entry in self.get_backlog()] + \
            [{**entry, 'status': ESTIMATED} for entry in self.get_history()]

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
        """Shows the players' hands and records the turn's estimate (the most-picked card).

        The estimate goes to the next story of the backlog, or to a new unnamed story if the backlog is empty.
        """
        if self.__revealed:
            return
        self.__revealed = True
        votes = self.__votes()
        estimate = self.consensus([vote['card'] for vote in votes])
        if estimate is None:
            return
        if self.__backlog:
            entry = self.__backlog.pop(0)
        else:
            entry = {'id': self.__next_story_id, 'name': '', 'ref': None, 'url': None}
            self.__next_story_id += 1
        entry['estimate'] = self.__number(estimate)
        entry['votes'] = votes
        self.__history.append(entry)
        self.__turn_story_id = entry['id']

    def info(self) -> dict:
        return {
            'name': self.name,
            'deck': self.__deck.name,
            'revealed': self.__revealed,
            'history': self.get_history(),
            'total': self.get_total(),
            'backlog': self.get_backlog(),
            'current': self.get_current_story(),
        }
