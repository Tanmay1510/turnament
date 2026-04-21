import os
import json
import queue
import threading
import sqlite3
import traceback
from functools import wraps

from flask import (Flask, Response, g, jsonify, redirect, render_template,
                   request, session, url_for, make_response)
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection, init_db

# APP CONFIG
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()

# Error handler - log full errors
@app.errorhandler(Exception)
def handle_error(error):
    print(f"\n{'='*60}")
    print(f"ERROR: {error}")
    print(f"{'='*60}")
    traceback.print_exc()
    print(f"{'='*60}\n")
    return jsonify({'error': str(error)}), 500

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

# Database initialization flag
_db_initialized = False

@app.before_request
def check_db():
    global _db_initialized
    if not _db_initialized:
        try:
            db = get_db()
            db.execute("SELECT COUNT(*) FROM tournaments")
            _db_initialized = True
        except sqlite3.OperationalError:
            try:
                init_db()
                _db_initialized = True
            except Exception as e:
                print(f"Failed to initialize DB: {e}")
                traceback.print_exc()
                _db_initialized = False

# SSE (Server-Sent Events) for real-time
sse_clients = []
sse_lock = threading.Lock()

def broadcast_score(data):
    with sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait(data)
            except Exception:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)

@app.route('/api/score-stream')
def score_stream():
    q = queue.Queue()
    with sse_lock:
        sse_clients.append(q)

    def generate():
        try:
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            with sse_lock:
                if q in sse_clients:
                    sse_clients.remove(q)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

# DATABASE HELPERS
def get_db():
    if 'db' not in g:
        g.db = get_connection()
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

# AUTH DECORATOR
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def api_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# PUBLIC PAGE ROUTES
@app.route('/')
def home():
    db = get_db()
    matches = rows_to_list(db.execute('''
        SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
               t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        ORDER BY m.scheduled_at ASC, m.id ASC
    ''').fetchall())

    tournaments = rows_to_list(db.execute(
        'SELECT * FROM tournaments ORDER BY created_at DESC'
    ).fetchall())

    return render_template('home.html', matches=matches, tournaments=tournaments, active_page='home')

@app.route('/live')
@app.route('/live/<int:match_id>')
def live(match_id=None):
    db = get_db()
    matches = rows_to_list(db.execute('''
        SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
               t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.status = 'live'
        ORDER BY m.id ASC
    ''').fetchall())

    selected = None
    if match_id:
        selected = row_to_dict(db.execute('''
            SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
                   t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.id = ?
        ''', (match_id,)).fetchone())

    elif matches:
        selected = matches[0]

    return render_template('live.html', matches=matches, selected=selected, active_page='live')


@app.route('/standings')
def standings():
    db = get_db()
    tournaments = rows_to_list(db.execute('SELECT * FROM tournaments ORDER BY created_at DESC').fetchall())
    tid = request.args.get('tournament_id')
    standings_data = []
    selected_tournament = None

    if tournaments:
        selected_tournament = tournaments[0]
        if tid:
            for t in tournaments:
                if str(t['id']) == tid:
                    selected_tournament = t
                    break

    if not selected_tournament:
        return render_template('standings.html', tournaments=tournaments, standings=[], 
                               selected_tournament=None, active_page='standings')

    teams = rows_to_list(db.execute('SELECT * FROM teams WHERE tournament_id = ?', (selected_tournament['id'],)).fetchall())
    completed_matches = rows_to_list(db.execute(
        'SELECT * FROM matches WHERE tournament_id = ? AND status = ?',
        (selected_tournament['id'], 'completed')
    ).fetchall())
    all_matches = rows_to_list(db.execute(
        'SELECT * FROM matches WHERE tournament_id = ?',
        (selected_tournament['id'],)
    ).fetchall())

    sport = selected_tournament.get('sport', '')

    if sport in BOARD_GAMES:
        import json as _json
        for team in teams:
            pkey = f"p{team['id']}"
            stats = {}
            games_played = 0

            for m in all_matches:
                try:
                    gd = _json.loads(m.get('game_data') or '{}')
                except Exception:
                    gd = {}
                if not gd:
                    continue

                if not any(k.startswith(pkey + '_') for k in gd):
                    continue

                games_played += 1

                for k, v in gd.items():
                    if k.startswith(pkey + '_'):
                        field = k[len(pkey) + 1:]
                        stats[field] = v

            entry = {'team': team, 'games_played': games_played, 'stats': stats}

            if sport == 'business':
                entry['balance'] = stats.get('balance', 0) or 0
                entry['networth'] = stats.get('networth', 0) or 0
                entry['properties'] = int(stats.get('properties', 0) or 0)
                entry['houses'] = int(stats.get('houses', 0) or 0)
                entry['hotels'] = int(stats.get('hotels', 0) or 0)
                entry['loans'] = int(stats.get('loans', 0) or 0)
                entry['rent_in'] = int(stats.get('rent_in', 0) or 0)
                entry['jail'] = int(stats.get('jail', 0) or 0)
                entry['bankrupt'] = stats.get('bankrupt') == 'yes'

            elif sport == 'ludo':
                entry['home'] = int(stats.get('home', 0) or 0)
                entry['kills'] = int(stats.get('kills', 0) or 0)
                entry['rolls'] = int(stats.get('rolls', 0) or 0)
                entry['sixes'] = int(stats.get('sixes', 0) or 0)

            elif sport == 'snake_ladders':
                entry['position'] = int(stats.get('position', 0) or 0)
                entry['snakes'] = int(stats.get('snakes', 0) or 0)
                entry['ladders'] = int(stats.get('ladders', 0) or 0)
                entry['rolls'] = int(stats.get('rolls', 0) or 0)

            standings_data.append(entry)

        if sport == 'business':
            standings_data.sort(key=lambda x: (not x['bankrupt'], -(x['networth'] or 0), -(x['balance'] or 0)))
        elif sport == 'ludo':
            standings_data.sort(key=lambda x: (-x['home'], -x['kills']))
        elif sport == 'snake_ladders':
            standings_data.sort(key=lambda x: (-x['position'], -x['ladders']))

    else:
        for team in teams:
            played = [m for m in completed_matches if m['team1_id'] == team['id'] or m['team2_id'] == team['id']]
            wins = len([m for m in played if m['winner_id'] == team['id']])
            losses = len([m for m in played if m['winner_id'] and m['winner_id'] != team['id']])
            draws = len(played) - wins - losses

            standings_data.append({
                **team,
                'played': len(played),
                'wins': wins,
                'losses': losses,
                'draws': draws,
                'points': wins * 3 + draws * 1,
            })

        standings_data.sort(key=lambda x: (-x['points'], -x['wins']))

    return render_template('standings.html',
        tournaments=tournaments, standings=standings_data,
        selected_tournament=selected_tournament, active_page='standings')


@app.route('/teams')
def teams_page():
    db = get_db()
    teams = rows_to_list(db.execute('SELECT * FROM teams ORDER BY name').fetchall())
    return render_template('teams.html', teams=teams, active_page='teams')


@app.route('/teams/<int:team_id>')
def team_detail(team_id):
    db = get_db()
    team = row_to_dict(db.execute('SELECT * FROM teams WHERE id = ?', (team_id,)).fetchone())
    if not team:
        return redirect(url_for('teams_page'))
    players = rows_to_list(db.execute('SELECT * FROM players WHERE team_id = ? ORDER BY number', (team_id,)).fetchall())
    return render_template('team_detail.html', team=team, players=players, active_page='teams')


@app.route('/bracket')
def bracket():
    db = get_db()
    tournaments = rows_to_list(db.execute('SELECT * FROM tournaments ORDER BY created_at DESC').fetchall())
    tid = request.args.get('tournament_id')
    selected_tournament = None
    matches = []

    if tournaments:
        selected_tournament = tournaments[0]
        if tid:
            for t in tournaments:
                if str(t['id']) == tid:
                    selected_tournament = t
                    break

        matches = rows_to_list(db.execute('''
            SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
                   t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
            FROM matches m
                        JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.tournament_id = ?
            ORDER BY m.id ASC
        ''', (selected_tournament['id'],)).fetchall())

    group_matches = [m for m in matches if m['match_type'] == 'group']
    knockout_matches = [m for m in matches if m['match_type'] != 'group']

    return render_template('bracket.html',
        tournaments=tournaments, group_matches=group_matches,
        knockout_matches=knockout_matches, selected_tournament=selected_tournament,
        active_page='bracket')


# ADMIN PAGE ROUTES

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin/login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    if not username or not password:
        return render_template('admin/login.html', error='Username and password required')

    db = get_db()
    admin = row_to_dict(db.execute('SELECT * FROM admin WHERE username = ?', (username,)).fetchone())
    if not admin or not check_password_hash(admin['password_hash'], password):
        return render_template('admin/login.html', error='Invalid credentials')

    session['admin_id'] = admin['id']
    session['admin_username'] = admin['username']
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'tournaments': db.execute('SELECT COUNT(*) FROM tournaments').fetchone()[0],
        'teams': db.execute('SELECT COUNT(*) FROM teams').fetchone()[0],
        'matches': db.execute('SELECT COUNT(*) FROM matches').fetchone()[0],
        'players': db.execute('SELECT COUNT(*) FROM players').fetchone()[0],
        'live': db.execute("SELECT COUNT(*) FROM matches WHERE status = 'live'").fetchone()[0],
    }
    return render_template('admin/dashboard.html', stats=stats, active_admin='dashboard')


@app.route('/admin/tournaments')
@admin_required
def admin_manage_tournaments():
    db = get_db()
    tournaments = rows_to_list(db.execute('SELECT * FROM tournaments ORDER BY created_at DESC').fetchall())
    for t in tournaments:
        t['team_count'] = db.execute('SELECT COUNT(*) FROM teams WHERE tournament_id = ?', (t['id'],)).fetchone()[0]
        t['match_count'] = db.execute('SELECT COUNT(*) FROM matches WHERE tournament_id = ?', (t['id'],)).fetchone()[0]
        t['player_count'] = db.execute('SELECT COUNT(*) FROM players p JOIN teams te ON p.team_id = te.id WHERE te.tournament_id = ?', (t['id'],)).fetchone()[0]
    return render_template('admin/manage_tournaments.html', tournaments=tournaments, active_admin='manage')


@app.route('/admin/tournament/create', methods=['GET', 'POST'])
@admin_required
def admin_create_tournament():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        sport = request.form.get('sport', '').strip()
        custom_sport = request.form.get('custom_sport', '').strip()
        final_sport = custom_sport if sport == 'Other' else sport

        if not name or not final_sport:
            return render_template('admin/create_tournament.html', error='Name and sport required', active_admin='create')

        db = get_db()
        db.execute('INSERT INTO tournaments (name, sport) VALUES (?, ?)', (name, final_sport))
        db.commit()
        return render_template('admin/create_tournament.html', success='Tournament created!', active_admin='create')

    return render_template('admin/create_tournament.html', active_admin='create')


@app.route('/admin/teams')
@admin_required
def admin_teams():
    db = get_db()
    tournaments = rows_to_list(db.execute('SELECT * FROM tournaments ORDER BY created_at DESC').fetchall())
    tid = request.args.get('tournament_id')
    selected_tournament = None
    teams = []

    if tournaments:
        selected_tournament = tournaments[0]
        if tid:
            for t in tournaments:
                if str(t['id']) == tid:
                    selected_tournament = t
                    break

    teams = rows_to_list(db.execute('SELECT * FROM teams WHERE tournament_id = ? ORDER BY name', (selected_tournament['id'],)).fetchall())
    for team in teams:
        team['players'] = rows_to_list(db.execute('SELECT * FROM players WHERE team_id = ? ORDER BY number', (team['id'],)).fetchall())

    is_board_game = selected_tournament and selected_tournament.get('sport', '') in BOARD_GAMES

    return render_template('admin/teams.html',
        tournaments=tournaments, teams=teams,
        selected_tournament=selected_tournament, active_admin='teams',
        is_board_game=is_board_game)


@app.route('/admin/schedule')
@admin_required
def admin_schedule():
    db = get_db()
    tournaments = rows_to_list(db.execute('SELECT * FROM tournaments ORDER BY created_at DESC').fetchall())
    tid = request.args.get('tournament_id')
    selected_tournament = None
    matches = []

    if tournaments:
        selected_tournament = tournaments[0]
        if tid:
            for t in tournaments:
                if str(t['id']) == tid:
                    selected_tournament = t
                    break

        matches = rows_to_list(db.execute('''
            SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
                   t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.tournament_id = ?
            ORDER BY m.id
        ''', (selected_tournament['id'],)).fetchall())

    all_teams = []
    if selected_tournament and selected_tournament.get('sport', '') in BOARD_GAMES:
        all_teams = rows_to_list(db.execute('SELECT * FROM teams WHERE tournament_id = ? ORDER BY id', (selected_tournament['id'],)).fetchall())

    return render_template('admin/schedule.html',
        tournaments=tournaments, matches=matches,
        selected_tournament=selected_tournament, active_admin='schedule',
        all_teams=all_teams)


@app.route('/admin/live-score')
@admin_required
def admin_live_score():
    db = get_db()
    tournaments = rows_to_list(db.execute('SELECT * FROM tournaments ORDER BY created_at DESC').fetchall())
    tid = request.args.get('tournament_id')
    selected_tournament = None
    matches = []

    if tournaments:
        selected_tournament = tournaments[0]
        if tid:
            for t in tournaments:
                if str(t['id']) == tid:
                    selected_tournament = t
                    break
        matches = rows_to_list(db.execute('''
        SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
               t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.tournament_id = ?
        ORDER BY m.id
    ''', (selected_tournament['id'],)).fetchall())

    import json as _json
    for m in matches:
        try:
            m['game_data'] = _json.loads(m.get('game_data') or '{}')
        except Exception:
            m['game_data'] = {}

    # For board games, pass all teams so we can show all players per round
    all_teams = []
    if selected_tournament and selected_tournament.get('sport', '') in BOARD_GAMES:
        all_teams = rows_to_list(db.execute(
            'SELECT * FROM teams WHERE tournament_id = ? ORDER BY id',
            (selected_tournament['id'],)
        ).fetchall())

    return render_template('admin/live_score.html',
        tournaments=tournaments, matches=matches,
        selected_tournament=selected_tournament, active_admin='live_score',
        all_teams=all_teams)


# API ROUTES (AJAX)

@app.route('/api/tournaments')
def api_tournaments():
    db = get_db()
    return jsonify(rows_to_list(db.execute('SELECT * FROM tournaments ORDER BY created_at DESC').fetchall()))


@app.route('/api/tournaments/<int:tid>', methods=['DELETE'])
@api_auth_required
def api_delete_tournament(tid):
    db = get_db()
    db.execute('DELETE FROM matches WHERE tournament_id = ?', (tid,))
    db.execute('DELETE FROM players WHERE team_id IN (SELECT id FROM teams WHERE tournament_id = ?)', (tid,))
    db.execute('DELETE FROM teams WHERE tournament_id = ?', (tid,))
    db.execute('DELETE FROM tournaments WHERE id = ?', (tid,))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/teams', methods=['GET', 'POST'])
def api_teams():
    db = get_db()
    tid = request.args.get('tournament_id')

    if request.method == 'GET':
        if tid:
            return jsonify(rows_to_list(db.execute(
                'SELECT * FROM teams WHERE tournament_id = ? ORDER BY name', (tid,)
            ).fetchall()))
        return jsonify(rows_to_list(db.execute('SELECT * FROM teams ORDER BY name').fetchall()))

    # POST - add team
    data = request.get_json()
    if not data or not data.get('tournament_id') or not data.get('name'):
        return jsonify({'error': 'tournament_id and name required'}), 400

    short = data.get('short_name', data['name'][:3].upper())
    color = data.get('color', '#3B82F6')

    db.execute(
        'INSERT INTO teams (tournament_id, name, short_name, color) VALUES (?, ?, ?, ?)',
        (data['tournament_id'], data['name'], short, color)
    )
    db.commit()
    return jsonify({'success': True}), 201


@app.route('/api/teams/<int:team_id>', methods=['DELETE'])
@api_auth_required
def api_delete_team(team_id):
    db = get_db()
    db.execute('DELETE FROM teams WHERE id = ?', (team_id,))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/players', methods=['POST'])
@api_auth_required
def api_add_player():
    data = request.get_json()
    if not data or not data.get('team_id') or not data.get('name'):
        return jsonify({'error': 'team_id and name required'}), 400

    db = get_db()
    db.execute(
        'INSERT INTO players (team_id, name, number, role) VALUES (?, ?, ?, ?)',
        (data['team_id'], data['name'], data.get('number'), data.get('role', 'player'))
    )
    db.commit()
    return jsonify({'success': True}), 201


@app.route('/api/players/<int:player_id>', methods=['DELETE'])
@api_auth_required
def api_delete_player(player_id):
    db = get_db()
    db.execute('DELETE FROM players WHERE id = ?', (player_id,))
    db.commit()
    return jsonify({'success': True})


BOARD_GAMES = {'business', 'ludo', 'snake_ladders'}


@app.route('/api/matches/generate', methods=['POST'])
@api_auth_required
def api_generate_matches():
    data = request.get_json()
    tid = data.get('tournament_id') if data else None

    if not tid:
        return jsonify({'error': 'tournament_id required'}), 400

    db = get_db()
    tournament = row_to_dict(db.execute(
        'SELECT * FROM tournaments WHERE id = ?', (tid,)
    ).fetchone())

    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404

    teams = rows_to_list(db.execute(
        'SELECT * FROM teams WHERE tournament_id = ?', (tid,)
    ).fetchall())

    if len(teams) < 2:
        return jsonify({'error': 'Need at least 2 players/teams'}), 400

    # Clear existing matches
    db.execute('DELETE FROM matches WHERE tournament_id = ?', (tid,))

    sport = tournament.get('sport', '')

    if sport in BOARD_GAMES:
        num_rounds = data.get('rounds', 3)
        for r in range(1, num_rounds + 1):
            db.execute(
                'INSERT INTO matches (tournament_id, team1_id, team2_id, match_type) VALUES (?, ?, ?, ?)',
                (tid, teams[0]['id'], teams[1]['id'], f'round_{r}')
            )
    else:
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                db.execute(
                    'INSERT INTO matches (tournament_id, team1_id, team2_id, match_type) VALUES (?, ?, ?, ?)',
                    (tid, teams[i]['id'], teams[j]['id'], 'group')
                )

    db.commit()

    matches = rows_to_list(db.execute('''
        SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
               t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.tournament_id = ?
    ''', (tid,)).fetchall())

    return jsonify(matches), 201


@app.route('/api/matches/<int:match_id>/score', methods=['PUT'])
@api_auth_required
def api_update_score(match_id):
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data'}), 400

    import json as _json
    game_data_str = None

    if 'game_data' in data:
        game_data_str = _json.dumps(data['game_data'])
    db = get_db()

    if game_data_str is not None:
        db.execute("""UPDATE matches SET
            score1 = COALESCE(?, score1), score2 = COALESCE(?, score2),
            status = COALESCE(?, status), winner_id = ?, game_data = ?
            WHERE id = ?""",
            (data.get('score1'), data.get('score2'),
             data.get('status'), data.get('winner_id'),
             game_data_str, match_id))
    else:
        db.execute("""UPDATE matches SET
            score1 = COALESCE(?, score1), score2 = COALESCE(?, score2),
            status = COALESCE(?, status), winner_id = ?
            WHERE id = ?""",
            (data.get('score1'), data.get('score2'),
             data.get('status'), data.get('winner_id'),
             match_id))

    db.commit()

    match = row_to_dict(db.execute('''
        SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
               t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.id = ?
    ''', (match_id,)).fetchone())

    broadcast_score(match)
    return jsonify(match)


@app.route('/api/matches')
def api_matches():
    db = get_db()
    tid = request.args.get('tournament_id')
    status = request.args.get('status')

    query = """SELECT m.*, t1.name as team1_name, t1.short_name as team1_short, t1.color as team1_color,
                      t2.name as team2_name, t2.short_name as team2_short, t2.color as team2_color
               FROM matches m
               JOIN teams t1 ON m.team1_id = t1.id
               JOIN teams t2 ON m.team2_id = t2.id WHERE 1=1"""
    params = []

    if tid:
        query += " AND m.tournament_id = ?"
        params.append(tid)

    if status:
        query += " AND m.status = ?"
        params.append(status)

    query += " ORDER BY m.id"
    return jsonify(rows_to_list(db.execute(query, params).fetchall()))


# START
if __name__ == '__main__':
    init_db()
    print("\n Server running on http://localhost:5000")
    print(" Admin panel: http://localhost:5000/admin/login")
    print(" Login: admin / admin123\n")
    app.run(host='0.0.0.0', port=5000, debug=True)

