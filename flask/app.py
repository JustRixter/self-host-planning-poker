import errno
import os
import secrets
import sys
import uuid

from flask import Flask, request, session, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, emit
from peewee import SqliteDatabase, OperationalError

from permission_check import check_db_file_permissions
from gamestate.exceptions import PlanningPokerException
from gamestate.game_manager import GameManager
from gamestate.models import database_proxy, StoredGame

app = Flask(__name__)
# Set SECRET_KEY to keep it stable across restarts; otherwise a random one is generated at startup
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or secrets.token_hex(32)

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
StoredGame.create_table()

gm = GameManager()

app_root = os.getenv('APP_ROOT', '/')
if not app_root.endswith('/'):
    app_root += '/'


@app.route('/create', methods=['POST'])
def create():
    body = request.json
    game_name = body['name']
    game_deck = body['deck']
    return gm.create(game_name, game_deck)


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
