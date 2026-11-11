import errno
import os
import secrets
import sys
import uuid
from urllib.parse import urlparse

from flask import Flask, request, session, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.middleware.proxy_fix import ProxyFix
from peewee import SqliteDatabase, OperationalError

from permission_check import check_db_file_permissions
from gamestate.exceptions import PlanningPokerException
from gamestate.game_manager import GameManager
from gamestate.models import database_proxy, create_tables
from mcp_server import McpServer
from rate_limit import RateLimiter, parse_rate

app = Flask(__name__)
# Set SECRET_KEY to keep it stable across restarts; otherwise a random one is generated at startup
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or secrets.token_hex(32)
# Largest request body accepted (413 above): 200 stories added to a backlog at once, with long names and links, fit
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024

# Behind reverse proxies, trust the X-Forwarded-* headers they set (one per proxy): the address of each player is then
# the real one and not the proxy's, which the rate limit of the creation of games needs
trusted_proxies = int(os.getenv('TRUSTED_PROXIES', '0'))
if trusted_proxies > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxies, x_proto=trusted_proxies, x_host=trusted_proxies)

# Games are created without an account: limit how many one address can create, so that nobody fills the database
create_rate = parse_rate(os.getenv('CREATE_RATE_LIMIT'), '20/hour')
create_limiter = RateLimiter(*create_rate) if create_rate else None

if app.config['DEBUG']:
    real_db = SqliteDatabase('database.db')
    socketio = SocketIO(app, cors_allowed_origins=[
        'http://localhost:4200', 'http://localhost:5000',
        'http://127.0.0.1:4200', 'http://127.0.0.1:5000'
    ])
    CORS(app)
else:
    check_db_file_permissions()
    real_db = SqliteDatabase('/data/database.db')
    socketio = SocketIO(app)
database_proxy.initialize(real_db)
if database_proxy.is_closed():
    database_proxy.connect()
create_tables()

gm = GameManager()

app_root = os.getenv('APP_ROOT', '/')
if not app_root.endswith('/'):
    app_root += '/'

# The MCP server (/mcp) lets AI agents read and prepare the stories of the rooms whose players turned on
# "AI agent access", with the agent link of the room. MCP_ENABLED=false turns it off for the whole server.
mcp_enabled = os.getenv('MCP_ENABLED', 'true').strip().lower() not in ('false', '0', 'no', 'off')


def room_link(room_id: str) -> str:
    return f"{request.host_url.rstrip('/')}{app_root}game/{room_id}"


def agent_link(room_id: str, key: str) -> str:
    return f'{room_link(room_id)}?agent={key}'


def notify_room(room_id: str, info: dict, activity: dict) -> None:
    """Tells the players of a room that an AI agent changed its stories"""
    socketio.emit('info', info, to=room_id)
    socketio.emit('agent_activity', activity, to=room_id)


mcp = McpServer(gm, notify_room, room_link)


def mcp_request_refused():
    """The response refusing a request to the MCP server, or None if it is allowed"""
    if not mcp_enabled:
        return jsonify({'error': 'The MCP server is turned off on this server'}), 404
    origin = request.headers.get('Origin')
    # Browsers send an Origin: other websites must not use the MCP server of a server on the network of a player
    if origin and urlparse(origin).netloc != request.host:
        return jsonify({'error': 'Cross-origin requests are not allowed'}), 403
    return None


@app.route('/create', methods=['POST'])
def create():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('name'), str) or not body['name'].strip() \
            or not isinstance(body.get('deck'), str):
        return jsonify({'error': 'Expected {"name": "<name of the game>", "deck": "<deck>"}'}), 400
    if create_limiter:
        retry_after = create_limiter.hit(request.remote_addr or 'unknown')
        if retry_after is not None:
            return jsonify({'error': 'Too many games created, try again later', 'retryAfter': retry_after}), 429, \
                {'Retry-After': str(retry_after)}
    try:
        return gm.create(body['name'], body['deck'])
    except PlanningPokerException as e:
        return jsonify({'error': str(e), 'code': e.code}), 400


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({'error': f"Request too large: {app.config['MAX_CONTENT_LENGTH'] // 1024} KB at most"}), 413


@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    refused = mcp_request_refused()
    if refused:
        return refused
    message = request.get_json(force=True, silent=True)
    if message is None:
        return jsonify({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}), 400
    # A server URL for a single room: /mcp?room=<room>&agent=<key>
    default_room = request.args.get('room')
    if default_room and request.args.get('agent'):
        default_room = f"{default_room}?agent={request.args['agent']}"
    response = mcp.handle(message, default_room=default_room)
    if response is None:
        return '', 202
    return jsonify(response)


@app.route('/mcp', methods=['GET', 'DELETE'])
def mcp_without_stream():
    # Stateless server: no stream of server-sent events to open, no session to end
    return jsonify({'error': 'Send JSON-RPC messages with POST'}), 405, {'Allow': 'POST'}


@app.route('/<string:file>.<string:ext>')
def serve_file(file, ext):
    return app.send_static_file(f'{file}.{ext}')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return render_template('index.html', app_root=app_root)


@app.route('/favicon.ico')
def serve_icon():
    return app.send_static_file('favicon/favicon.ico')

@app.route('/assets/<path:path>')
def serve_assets(path):
    return app.send_static_file(f'assets/{path}')

@socketio.event
def join(data):
    player_id = str(uuid.uuid4())
    session['player_id'] = player_id
    player_name = data['name']
    spectator = data['spectator']
    game_id = data['game']

    session['game_id'] = game_id
    join_room(game_id)

    info, state = gm.join_game(game_id, player_id, player_name, spectator)
    emit('state', state, to=game_id, json=True)

    info['playerId'] = player_id
    info['mcpAvailable'] = mcp_enabled
    return info


@socketio.event
def disconnect(reason=None):
    # Flask-SocketIO 5.5+ passes the reason of the disconnection to this handler: it must accept it,
    # otherwise the handler fails silently and the players who leave stay in the game forever.
    player_id = session.get('player_id')
    game_id = session.get('game_id')
    if not player_id or not game_id:
        return  # the client never joined a game

    try:
        state = gm.leave_game(game_id, player_id)
    except (PlanningPokerException, KeyError):
        return  # the game is not ongoing anymore, or the player already left
    leave_room(game_id)
    emit('state', state, to=game_id, json=True)

    session['player_id'] = None
    session['game_id'] = None


@socketio.event
def rename_game(data):
    game_id = session['game_id']
    game_name = data['name']

    info = gm.rename_game(game_id, game_name)
    emit('info', info, to=game_id, json=True)


@socketio.event
def set_deck(data):
    game_id = session['game_id']
    deck_name = data['deck']

    info, state = gm.set_deck(game_id, deck_name)
    emit('info', info, to=game_id, json=True)
    emit('state', state, to=game_id, json=True)


@socketio.event
def set_player_name(data):
    player_id = session['player_id']
    game_id = session['game_id']
    player_name = data['name']

    state = gm.set_player_name(game_id, player_id, player_name)
    emit('state', state, to=game_id, json=True)


@socketio.event
def set_spectator(data):
    player_id = session['player_id']
    game_id = session['game_id']
    is_spectator = data['spectator']

    state = gm.set_player_spectator(game_id, player_id, is_spectator)
    emit('state', state, to=game_id, json=True)


@socketio.event
def pick_card(data):
    player_id = session['player_id']
    game_id = session['game_id']
    card = data['card']

    state = gm.pick_card(game_id, player_id, card)
    emit('state', state, to=game_id, json=True)


@socketio.event
def update_story(data):
    game_id = session['game_id']

    info = gm.update_story(game_id, data['id'], data.get('name'), data.get('estimate'))
    emit('info', info, to=game_id, json=True)


@socketio.event
def delete_story(data):
    game_id = session['game_id']

    info = gm.delete_story(game_id, data['id'])
    emit('info', info, to=game_id, json=True)


@socketio.event
def add_to_backlog(data):
    game_id = session['game_id']

    info, _ = gm.add_to_backlog(game_id, data['stories'])
    emit('info', info, to=game_id, json=True)


@socketio.event
def move_story(data):
    game_id = session['game_id']

    info = gm.move_story(game_id, data['id'], data['position'])
    emit('info', info, to=game_id, json=True)


@socketio.event
def skip_story():
    game_id = session['game_id']

    info = gm.skip_story(game_id)
    emit('info', info, to=game_id, json=True)


@socketio.event
def requeue_story(data):
    game_id = session['game_id']

    info = gm.requeue_story(game_id, data['id'])
    emit('info', info, to=game_id, json=True)


@socketio.event
def clear_backlog():
    game_id = session['game_id']

    info = gm.clear_backlog(game_id)
    emit('info', info, to=game_id, json=True)


@socketio.event
def enable_agent_access():
    """Lets AI agents in the room: answers the agent link to give them"""
    game_id = session['game_id']
    if not mcp_enabled:
        return {'error': True, 'message': 'The MCP server is turned off on this server', 'code': 4010}

    info, key = gm.enable_agent_access(game_id)
    emit('info', info, to=game_id, json=True)
    return {'link': agent_link(game_id, key)}


@socketio.event
def get_agent_link():
    """The agent link of the room, to show it again. None if agents are not let in."""
    game_id = session['game_id']

    key = gm.get_agent_key(game_id)
    return {'link': agent_link(game_id, key) if key and mcp_enabled else None}


@socketio.event
def renew_agent_link():
    """Replaces the agent link of the room: the agents that have the previous one cannot use it anymore"""
    game_id = session['game_id']
    if not mcp_enabled:
        return {'error': True, 'message': 'The MCP server is turned off on this server', 'code': 4010}

    info, key = gm.renew_agent_key(game_id)
    emit('info', info, to=game_id, json=True)
    return {'link': agent_link(game_id, key)}


@socketio.event
def disable_agent_access():
    game_id = session['game_id']

    info = gm.disable_agent_access(game_id)
    emit('info', info, to=game_id, json=True)


@socketio.event
def reveal_cards():
    game_id = session['game_id']

    state, info = gm.reveal_cards(game_id)
    emit('state', state, to=game_id, json=True)
    emit('info', info, to=game_id, json=True)


@socketio.event
def end_turn():
    game_id = session['game_id']

    state, info = gm.end_turn(game_id)
    emit('state', state, to=game_id, json=True)
    emit('info', info, to=game_id, json=True)
    emit('new_game', to=game_id)


@socketio.on_error()
def on_error_handler(e):
    body = {'error': True, 'message': str(e), 'code': 0}
    if isinstance(e, PlanningPokerException):
        body['code'] = e.code
    return body


if __name__ == '__main__':
    socketio.run(app)
