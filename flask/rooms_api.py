"""Read-only views of a room for the MCP server: what an agent needs to know about the stories"""
import csv
import io
import re
from collections import Counter
from typing import Callable, Optional

from gamestate.deck import card_label, has_points
from gamestate.exceptions import GameDoesNotExistError
from gamestate.game import Game

ROOM_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
AGENT_KEY = re.compile(r'[?&#]agent=([A-Za-z0-9_-]+)')


def parse_agent_link(value) -> tuple[str, Optional[str]]:
    """The id of a room and the key of its agent link, from the link (https://<server>/game/<room>?agent=<key>)"""
    if not value or not isinstance(value, str):
        raise GameDoesNotExistError('No room given: pass the agent link of the room, which a player can copy in the '
                                    'room after turning on "AI agent access"')
    match = ROOM_ID.search(value)
    if not match:
        raise GameDoesNotExistError(f'{value!r} is not the agent link of a room')
    key = AGENT_KEY.search(value)
    return match.group(0).lower(), key.group(1) if key else None


def _agreement(votes: list[dict]) -> Optional[float]:
    """Share of the players who picked the most picked card, as in the summary of a turn"""
    if not votes:
        return None
    return round(max(Counter(vote['card'] for vote in votes).values()) / len(votes), 2)


def story_view(game: Game, entry: dict, position: int) -> dict:
    deck = game.get_deck()
    view = {
        'id': entry['id'],
        'position': position,
        'name': entry['name'],
        'ref': entry['ref'],
        'url': entry['url'],
    }
    if 'estimate' in entry:
        votes = entry.get('votes') or []
        view.update({
            'estimate': entry['estimate'],
            'estimate_label': card_label(deck, entry['estimate']),
            'votes': [{'player': vote['player'], 'card': card_label(deck, vote['card'])} for vote in votes],
            'agreement': _agreement(votes),
            'lowest_vote': card_label(deck, min(vote['card'] for vote in votes)) if votes else None,
            'highest_vote': card_label(deck, max(vote['card'] for vote in votes)) if votes else None,
        })
    return view


def stories_view(game: Game) -> dict:
    deck = game.get_deck()
    return {
        'deck': deck.name,
        'total': game.get_total() if has_points(deck) else None,
        'stories': [story_view(game, entry, i + 1) for i, entry in enumerate(game.get_history())],
    }


def backlog_view(game: Game) -> dict:
    return {'backlog': [story_view(game, entry, i + 1) for i, entry in enumerate(game.get_backlog())]}


def room_view(game: Game, room_id: str, room_link: Callable[[str], str]) -> dict:
    current = game.get_current_story()
    deck = game.get_deck()
    return {
        'room': room_id,
        'link': room_link(room_id),
        'name': game.name,
        'deck': deck.name,
        'cards': [card_label(deck, card) for card in deck.value],
        'revealed': game.get_revealed(),
        'players': [{'name': player.name, 'spectator': player.spectator, 'voted': player.has_picked_card()}
                    for _, player in game.list_players()],
        'current_story': story_view(game, current, 0) if current else None,
        'backlog_size': len(game.get_backlog()),
        'estimated_count': len(game.get_history()),
        'total': game.get_total() if has_points(deck) else None,
    }


EXPORT_HEADER = ['#', 'Ref', 'Story', 'Estimate', 'Votes', 'Link']


def _export_rows(game: Game) -> list[list[str]]:
    rows = []
    for view in stories_view(game)['stories']:
        votes = ', '.join(f"{vote['player']}: {vote['card']}" for vote in view['votes'])
        rows.append([str(view['position']), view['ref'] or '', view['name'] or f"Story {view['position']}",
                     view['estimate_label'], votes, view['url'] or ''])
    return rows


def to_csv(game: Game) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(EXPORT_HEADER)
    writer.writerows(_export_rows(game))
    return output.getvalue()


def to_markdown(game: Game) -> str:
    def cell(text: str) -> str:
        return text.replace('\\', '\\\\').replace('|', '\\|')

    lines = [f'## {cell(game.name)}', '',
             '| ' + ' | '.join(EXPORT_HEADER) + ' |',
             '|' + '---|' * len(EXPORT_HEADER)]
    lines += ['| ' + ' | '.join(cell(value) for value in row) + ' |' for row in _export_rows(game)]
    if has_points(game.get_deck()):
        lines += ['', f'**Total:** {card_label(game.get_deck(), game.get_total())} points']
    return '\n'.join(lines) + '\n'
