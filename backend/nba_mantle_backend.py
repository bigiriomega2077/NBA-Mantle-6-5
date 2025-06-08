from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from difflib import get_close_matches
import json
import os
import random

app = Flask(__name__, static_folder='build', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Load players database
def load_players_db():
    try:
        with open('players_awards.json', encoding='utf-8') as f:
            data = json.load(f)
            # Convert to list format that frontend expects
            players_list = []
            for name, player_data in data.items():
                # Calculate start year from seasons if not present
                start_year = player_data.get('start_year', 0)
                if start_year == 0 and player_data.get('seasons'):
                    # Get the earliest season year
                    seasons = player_data.get('seasons', [])
                    if seasons:
                        start_year = min(season.get('season', 9999) for season in seasons)
                
                player_entry = {
                    'name': name,
                    'start_year': start_year,
                    'career_length': len(player_data.get('seasons', [])),
                    'data': player_data
                }
                players_list.append(player_entry)
            return data, players_list
    except FileNotFoundError:
        print("Warning: players_awards.json not found. Using empty database.")
        return {}, []

players_db, players_list = load_players_db()
guess_counter = {}

def get_filtered_players(game_mode='all-time'):
    """Filter players based on game mode"""
    if game_mode == 'classic':
        # Filter for players who started in 2011+ with 5+ seasons
        filtered = [
            player for player in players_list 
            if player['start_year'] >= 2011 and player['career_length'] >= 5
        ]
        return [player['name'] for player in filtered]
    else:
        # All time mode - return all players
        return [player['name'] for player in players_list]

def compute_similarity(player1, player2, name1=None, name2=None):
    score = 0
    breakdown = {}

    # Shared seasons
    p1_seasons = set((s["team"], s["season"]) for s in player1.get("seasons", []))
    p2_seasons = set((s["team"], s["season"]) for s in player2.get("seasons", []))
    shared_seasons = sorted(p1_seasons & p2_seasons, key=lambda x: x[1])
    shared_season_count = len(shared_seasons)

    consecutive_bonus = 0
    if shared_season_count >= 2:
        years = [s for _, s in shared_seasons]
        streak = 1
        max_streak = 1
        for i in range(1, len(years)):
            if years[i] == years[i-1] + 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        consecutive_bonus = min(max_streak * 2, 10)

    if shared_season_count >= 6:
        pts = 50
    elif shared_season_count >= 4:
        pts = 40
    elif shared_season_count >= 2:
        pts = 30
    elif shared_season_count == 1:
        pts = 20
    else:
        pts = 0

    score += pts + consecutive_bonus
    breakdown["shared_seasons"] = pts
    breakdown["shared_streak_bonus"] = consecutive_bonus

    # Teammate years
    teammate_years = player1.get("teammate_years", {}).get(name2, 0)
    if teammate_years >= 6:
        pts = 15
    elif teammate_years >= 4:
        pts = 10
    elif teammate_years >= 2:
        pts = 6
    elif teammate_years == 1:
        pts = 3
    else:
        pts = 0
    score += pts
    breakdown["teammate_years"] = pts

    # Shared franchises
    overlap_teams = set(player1.get("teams", [])) & set(player2.get("teams", []))
    team_pts = len(overlap_teams) * 2
    score += team_pts
    breakdown["shared_teams"] = team_pts

    # Tenure overlap
    tenure_bonus = 0
    for team in overlap_teams:
        p1_years = {s["season"] for s in player1["seasons"] if s["team"] == team}
        p2_years = {s["season"] for s in player2["seasons"] if s["team"] == team}
        overlap = len(p1_years & p2_years)
        tenure_bonus += min(overlap, 3)
    score += tenure_bonus
    breakdown["team_tenure"] = tenure_bonus

    # Position match
    p1_pos = player1.get("position", "")
    p2_pos = player2.get("position", "")
    if p1_pos == p2_pos:
        pts = 8
    elif p1_pos[:2] == p2_pos[:2]:
        pts = 2
    else:
        pts = 0
    score += pts
    breakdown["position_match"] = pts

    # Start year (era proximity with exact match bonus)
    start1 = player1.get("start_year", 0)
    start2 = player2.get("start_year", 0)
    era_diff = abs(start1 - start2)

    if era_diff == 0:
        era_pts = 6  # Big bonus for same start year
    elif era_diff <= 5:
        era_pts = 4
    elif era_diff <= 10:
        era_pts = 2
    else:
        era_pts = 0

    score += era_pts
    breakdown["start_year_diff"] = era_pts

    # All-Star (once)
    if set(player1.get("all_star_seasons", [])) & set(player2.get("all_star_seasons", [])):
        score += 3
        breakdown["shared_all_star"] = 3

    # All-NBA/Defense/Rookie team (once)
    found_team = False
    for sel1 in player1.get("all_team_selections", []):
        for sel2 in player2.get("all_team_selections", []):
            if sel1["season"] == sel2["season"] and sel1["type"] == sel2["type"]:
                found_team = True
                break
        if found_team:
            break
    if found_team:
        score += 3
        breakdown["shared_all_team"] = 3

    # Shared award winners (once)
    if set(player1.get("awards_won", [])) & set(player2.get("awards_won", [])):
        score += 5
        breakdown["shared_awards"] = 5

    breakdown["total"] = min(score, 99)
    return breakdown["total"], breakdown

def get_player(name):
    name = name.strip().lower()
    for player in players_db:
        if player.lower() == name:
            return players_db[player], player
    close = get_close_matches(name, players_db.keys(), n=1, cutoff=0.8)
    if close:
        return players_db[close[0]], close[0]
    return None, None

# Serve React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# API Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'Server is running', 'players_loaded': len(players_db)})

@app.route('/api/players', methods=['GET', 'POST'])
def get_players():
    """Return list of players based on game mode"""
    if request.method == 'POST':
        try:
            data = request.json or {}
            game_mode = data.get('mode', 'all-time')
        except:
            game_mode = 'all-time'
    else:
        game_mode = request.args.get('mode', 'all-time')
    
    # Return the structured data format that frontend expects
    if game_mode == 'classic':
        filtered_players = [
            player for player in players_list 
            if player['start_year'] >= 2011 and player['career_length'] >= 5
        ]
    else:
        filtered_players = players_list
    
    return jsonify(filtered_players)

@app.route('/api/player_names', methods=['GET', 'POST'])
def get_player_names():
    """Return list of player names based on game mode"""
    if request.method == 'POST':
        try:
            data = request.json or {}
            game_mode = data.get('mode', 'all-time')
        except:
            game_mode = 'all-time'
    else:
        game_mode = request.args.get('mode', 'all-time')
    
    filtered_names = get_filtered_players(game_mode)
    return jsonify(filtered_names)

@app.route('/api/player_awards', methods=['GET'])
def get_player_awards():
    """Return list of all player names (for compatibility with frontend)"""
    return jsonify(list(players_db.keys()))

@app.route('/api/players_data', methods=['GET'])
def get_players_data():
    """Return full player database for filtering"""
    return jsonify(players_db)

@app.route('/api/guess', methods=['POST'])
def guess():
    try:
        data = request.json or {}
        guess_input = data.get('guess', '').strip()
        target_input = data.get('target', '').strip()
        game_mode = data.get('mode', 'all-time')  # Get game mode from request

        if not guess_input or not target_input:
            return jsonify({"error": "Missing guess or target player."}), 400

        guess_player, guess_key = get_player(guess_input)
        target_player, target_key = get_player(target_input)

        if not guess_player or not target_player:
            missing_player = "guess" if not guess_player else "target"
            player_name = guess_input if not guess_player else target_input
            return jsonify({"error": f"Invalid {missing_player} player name: '{player_name}'."}), 400

        # Validate that both players are allowed in the current game mode
        allowed_players = get_filtered_players(game_mode)
        if guess_key not in allowed_players:
            return jsonify({"error": f"Player '{guess_key}' is not available in {game_mode} mode."}), 400
        if target_key not in allowed_players:
            return jsonify({"error": f"Target player '{target_key}' is not available in {game_mode} mode."}), 400

        guess_counter[target_key] = guess_counter.get(target_key, 0) + 1

        if guess_key == target_key:
            # Calculate top 5 similar players from the same game mode
            similarities = []
            for other_name in allowed_players:
                if other_name == target_key:
                    continue
                other_data = players_db.get(other_name)
                if other_data:
                    sim_score, _ = compute_similarity(other_data, target_player, other_name, target_key)
                    similarities.append((other_name, sim_score))
            
            top_5 = sorted(similarities, key=lambda x: x[1], reverse=True)[:5]

            return jsonify({
                "score": 100,
                "message": "🔥 You got it!",
                "matched_name": guess_key,
                "top_5": top_5,
                "mode": game_mode
            })

        score, breakdown = compute_similarity(guess_player, target_player, guess_key, target_key)

        return jsonify({
            "score": score,
            "matched_name": guess_key,
            "breakdown": breakdown,
            "mode": game_mode
        })

    except Exception as e:
        print(f"Error in guess endpoint: {e}")
        return jsonify({"error": "Internal server error occurred."}), 500

@app.route('/api/random_player', methods=['POST'])
def get_random_player():
    """Get a random player for the specified game mode"""
    try:
        data = request.json or {}
        game_mode = data.get('mode', 'all-time')
        
        allowed_players = get_filtered_players(game_mode)
        if not allowed_players:
            return jsonify({"error": "No players available for this game mode"}), 400
        
        random_player = random.choice(allowed_players)
        
        return jsonify({
            "player": random_player,
            "mode": game_mode,
            "total_players": len(allowed_players)
        })
    
    except Exception as e:
        print(f"Error in random_player endpoint: {e}")
        return jsonify({"error": "Internal server error occurred."}), 500

# Debug endpoint to check player filtering
@app.route('/api/debug/players', methods=['GET'])
def debug_players():
    """Debug endpoint to see player filtering results"""
    all_time_players = get_filtered_players('all-time')
    classic_players = get_filtered_players('classic')
    
    # Sample of classic players with their stats
    classic_sample = []
    for player_name in classic_players[:10]:  # First 10 players
        player_entry = next((p for p in players_list if p['name'] == player_name), None)
        if player_entry:
            classic_sample.append({
                'name': player_name,
                'start_year': player_entry['start_year'],
                'career_length': player_entry['career_length']
            })
    
    return jsonify({
        'all_time_count': len(all_time_players),
        'classic_count': len(classic_players),
        'classic_sample': classic_sample,
        'total_players_loaded': len(players_list)
    })

if __name__ == '__main__':
    print("Starting NBA Similarity Game Backend...")
    print(f"Loaded {len(players_db)} total players")
    
    all_time_count = len(get_filtered_players('all-time'))
    classic_count = len(get_filtered_players('classic'))
    
    print(f"All-time mode players: {all_time_count}")
    print(f"Classic mode players: {classic_count}")
    
    if classic_count == 0:
        print("WARNING: No players found for classic mode! Check your data format.")
        # Show sample of player data for debugging
        sample_players = players_list[:3]
        for player in sample_players:
            print(f"Sample player: {player['name']}, start_year: {player['start_year']}, career_length: {player['career_length']}")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)