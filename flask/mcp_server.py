"""A Model Context Protocol (MCP) server, so that AI agents can read and prepare the stories of a room.

It speaks the stateless flavour of the Streamable HTTP transport: each POST carries one JSON-RPC message and gets
one JSON answer, without sessions or server-sent events. That is enough for tools, and it runs in the Flask process
which holds the games in memory.
"""
import json
from typing import Any, Callable, Optional

from gamestate.deck import card_from_label
from gamestate.exceptions import PlanningPokerException, InvalidCardValueError
from gamestate.game_manager import GameManager
from rooms_api import parse_agent_link, room_view, stories_view, backlog_view, to_markdown, to_csv

PROTOCOL_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05')
SERVER_INFO = {'name': 'self-host-planning-poker', 'title': 'Planning Poker', 'version': '1.0.0'}

INSTRUCTIONS = """\
Planning Poker rooms where a team estimates stories by voting with cards.
Every tool takes the room as its agent link: https://<server>/game/<room>?agent=<key>. The players of a room give
it once they turn on "AI agent access" in the room; the link to join the room is not enough. If a tool answers that
agents are not allowed, ask the user for the agent link of the room.
Stories waiting to be estimated are in the backlog: the first one is estimated at the next vote, and the
estimate (the most picked card, the highest one on a tie) is recorded with every player's vote.
Typical uses: fill the backlog from an issue tracker with add_to_backlog (keep the issue key in `ref` and its link
in `url`), then after the session read list_stories and write the estimates back to the tracker.
Stories with a low agreement or far apart votes are worth discussing again: requeue_story puts one back on top."""

ROOM_PROPERTY = {
    'type': 'string',
    'description': 'The agent link of the room: https://<server>/game/<room>?agent=<key>, copied from the room once '
                   'a player turned on "AI agent access". Optional if the URL of the server has ?room=<id>&agent=<key>.',
}
STORY_ID_PROPERTY = {'type': 'integer', 'description': 'The id of the story (not its position)'}


def _tool(name: str, title: str, description: str, properties: Optional[dict] = None,
          required: Optional[list] = None, read_only=False, destructive=False, idempotent=False) -> dict:
    return {
        'name': name,
        'title': title,
        'description': description,
        'inputSchema': {
            'type': 'object',
            'properties': {'room': ROOM_PROPERTY, **(properties or {})},
            'required': required or [],
            'additionalProperties': False,
        },
        'annotations': {
            'title': title,
            'readOnlyHint': read_only,
            'destructiveHint': destructive,
            'idempotentHint': idempotent,
            'openWorldHint': False,
        },
    }


TOOLS = [
    _tool('get_room', 'Get room',
          'Overview of a room: name, deck and its cards, players (and whether they voted), whether the cards are '
          'revealed, the story being estimated, the size of the backlog and the total of the estimates.',
          read_only=True, idempotent=True),
    _tool('list_stories', 'List estimated stories',
          'The stories estimated in the room, oldest first, with their estimate, every player\'s vote, the agreement '
          '(share of the players who picked the most picked card) and the lowest and highest votes. '
          'The total is null for t-shirt sizes.',
          read_only=True, idempotent=True),
    _tool('list_backlog', 'List backlog',
          'The stories waiting to be estimated, in order: position 1 is estimated at the next vote.',
          read_only=True, idempotent=True),
    _tool('add_to_backlog', 'Add stories to the backlog',
          'Adds stories at the end of the backlog. A story whose ref is already in the room is skipped, so it is '
          'safe to send the same issues again. The players see the backlog change at once.',
          {'stories': {
              'type': 'array',
              'minItems': 1,
              'maxItems': 200,
              'items': {
                  'type': 'object',
                  'properties': {
                      'name': {'type': 'string', 'description': 'Title of the story (100 characters at most)'},
                      'ref': {'type': 'string', 'description': 'Key of the issue in a tracker, such as ABC-123'},
                      'url': {'type': 'string', 'description': 'Link to the issue (http or https)'},
                  },
                  'additionalProperties': False,
              },
          }},
          ['stories']),
    _tool('update_story', 'Update a story',
          'Renames a story (in the backlog or estimated) and/or changes the estimate of an estimated story.',
          {'id': STORY_ID_PROPERTY,
           'name': {'type': 'string'},
           'estimate': {'type': ['number', 'string'],
                        'description': 'A card of the deck of the room: a number, or a label such as "XL"'}},
          ['id'], idempotent=True),
    _tool('move_story', 'Move a story of the backlog',
          'Moves a story of the backlog to a position: 1 makes it the next story to estimate.',
          {'id': STORY_ID_PROPERTY, 'position': {'type': 'integer', 'minimum': 1}},
          ['id', 'position'], idempotent=True),
    _tool('requeue_story', 'Vote again on a story',
          'Removes the estimate of a story and puts it on top of the backlog, so that the team votes on it again.',
          {'id': STORY_ID_PROPERTY}, ['id']),
    _tool('delete_story', 'Delete a story', 'Deletes a story, from the backlog or from the estimated stories.',
          {'id': STORY_ID_PROPERTY}, ['id'], destructive=True, idempotent=True),
    _tool('clear_backlog', 'Clear the backlog',
          'Removes every story of the backlog. The estimated stories are kept.', destructive=True, idempotent=True),
    _tool('export_stories', 'Export estimated stories',
          'The estimated stories as a Markdown table or as CSV, ready to paste in a document or a spreadsheet.',
          {'format': {'type': 'string', 'enum': ['markdown', 'csv'], 'default': 'markdown'}},
          read_only=True, idempotent=True),
]
TOOL_NAMES = {tool['name'] for tool in TOOLS}


class ToolInputError(Exception):
    pass


def _error(message_id, code: int, message: str) -> dict:
    return {'jsonrpc': '2.0', 'id': message_id, 'error': {'code': code, 'message': message}}


def _result(message_id, result: dict) -> dict:
    return {'jsonrpc': '2.0', 'id': message_id, 'result': result}


def _integer(arguments: dict, name: str) -> int:
    value = arguments.get(name)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ToolInputError(f'`{name}` must be an integer')
    return value


class McpServer:
    def __init__(self, gm: GameManager, notify: Callable[[str, dict, dict], None], room_link: Callable[[str], str]):
        """notify(room, info, activity) tells the players of a room that an agent changed its stories.
        activity: {'action': str, 'count'?: int, 'story'?: str}"""
        self.gm = gm
        self.notify = notify
        self.room_link = room_link

    def handle(self, message: Any, default_room: Optional[str] = None) -> Optional[dict]:
        """Answers a JSON-RPC message, or returns None for notifications and responses (nothing to answer)"""
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            return _error(None, -32600, 'Invalid request: expected a JSON-RPC 2.0 message')
        if 'method' not in message:
            return None  # a response to a request of ours: we never send any
        message_id = message.get('id')
        method = message['method']
        if 'id' not in message:
            return None  # notifications such as notifications/initialized need no answer
        params = message.get('params')
        if params is None:
            params = {}
        if not isinstance(method, str) or not isinstance(params, dict):
            return _error(message_id, -32600, 'Invalid request')

        if method == 'initialize':
            requested = params.get('protocolVersion')
            return _result(message_id, {
                'protocolVersion': requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': SERVER_INFO,
                'instructions': INSTRUCTIONS,
            })
        if method == 'ping':
            return _result(message_id, {})
        if method == 'tools/list':
            return _result(message_id, {'tools': TOOLS})
        if method == 'tools/call':
            name = params.get('name')
            arguments = params.get('arguments')
            if arguments is None:
                arguments = {}
            if name not in TOOL_NAMES or not isinstance(arguments, dict):
                return _error(message_id, -32602, f'Unknown tool: {name}')
            return _result(message_id, self.call_tool(name, arguments, default_room))
        return _error(message_id, -32601, f'Method not found: {method}')

    def call_tool(self, name: str, arguments: dict, default_room: Optional[str] = None) -> dict:
        try:
            room, key = parse_agent_link(arguments.get('room') or default_room)
            self.gm.authorize_agent(room, key)
            output = getattr(self, f'_tool_{name}')(room, arguments)
        except (PlanningPokerException, ToolInputError) as e:
            return {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}
        if isinstance(output, str):
            return {'content': [{'type': 'text', 'text': output}], 'isError': False}
        return {
            'content': [{'type': 'text', 'text': json.dumps(output, ensure_ascii=False, indent=2)}],
            'structuredContent': output,
            'isError': False,
        }

    # Tools: each one gets the id of the room and the arguments

    def _tool_get_room(self, room: str, _arguments: dict):
        return room_view(self.gm.get_for_stories(room), room, self.room_link)

    def _tool_list_stories(self, room: str, _arguments: dict):
        return {'room': room, **stories_view(self.gm.get_for_stories(room))}

    def _tool_list_backlog(self, room: str, _arguments: dict):
        return {'room': room, **backlog_view(self.gm.get_for_stories(room))}

    def _tool_add_to_backlog(self, room: str, arguments: dict):
        stories = arguments.get('stories')
        if not isinstance(stories, list) or not stories:
            raise ToolInputError('`stories` must be a list of stories: [{"name": ..., "ref": ..., "url": ...}]')
        info, result = self.gm.add_to_backlog(room, stories)
        if result['added']:
            self.notify(room, info, {'action': 'added', 'count': len(result['added'])})
        return {'room': room, **result, 'backlog_size': len(info['backlog'])}

    def _tool_update_story(self, room: str, arguments: dict):
        story_id = _integer(arguments, 'id')
        estimate = arguments.get('estimate')
        if estimate is not None:
            deck = self.gm.get_for_stories(room).get_deck()
            card = card_from_label(deck, estimate)
            if card is None:
                raise InvalidCardValueError(f'{estimate} is not a card of the deck {deck.name}')
            estimate = card
        info = self.gm.update_story(room, story_id, arguments.get('name'), estimate)
        self.notify(room, info, {'action': 'updated', 'story': self.__story_label(room, story_id)})
        return self.__story(room, story_id)

    def _tool_move_story(self, room: str, arguments: dict):
        info = self.gm.move_story(room, _integer(arguments, 'id'), _integer(arguments, 'position'))
        self.notify(room, info, {'action': 'moved'})
        return {'room': room, **backlog_view(self.gm.get_for_stories(room))}

    def _tool_requeue_story(self, room: str, arguments: dict):
        story_id = _integer(arguments, 'id')
        info = self.gm.requeue_story(room, story_id)
        self.notify(room, info, {'action': 'requeued', 'story': self.__story_label(room, story_id)})
        return {'room': room, **backlog_view(self.gm.get_for_stories(room))}

    def _tool_delete_story(self, room: str, arguments: dict):
        story_id = _integer(arguments, 'id')
        label = self.__story_label(room, story_id)
        info = self.gm.delete_story(room, story_id)
        self.notify(room, info, {'action': 'deleted', 'story': label})
        return {'room': room, 'deleted': story_id}

    def _tool_clear_backlog(self, room: str, _arguments: dict):
        info = self.gm.clear_backlog(room)
        self.notify(room, info, {'action': 'cleared'})
        return {'room': room, 'backlog_size': 0}

    def _tool_export_stories(self, room: str, arguments: dict):
        export_format = arguments.get('format') or 'markdown'
        if export_format not in ('markdown', 'csv'):
            raise ToolInputError('`format` must be markdown or csv')
        game = self.gm.get_for_stories(room)
        return to_csv(game) if export_format == 'csv' else to_markdown(game)

    def __story_label(self, room: str, story_id: int) -> str:
        """How the players know a story: 'ABC-1 Login timeout', or its id if it has neither ref nor name"""
        story = self.__story(room, story_id)['story']
        if not story:
            return f'#{story_id}'
        return ' '.join(part for part in (story['ref'], story['name']) if part) or f'#{story_id}'

    def __story(self, room: str, story_id: int) -> dict:
        game = self.gm.get_for_stories(room)
        for views in (stories_view(game)['stories'], backlog_view(game)['backlog']):
            for view in views:
                if view['id'] == story_id:
                    return {'room': room, 'story': view}
        return {'room': room, 'story': None}
