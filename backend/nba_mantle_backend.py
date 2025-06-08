from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from difflib import get_close_matches
import json
import os

app = Flask(__name__, static_folder='build', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Load players database
def load_players_db():
    try:
        with open('players_awards.json', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: players_awards.json not found. Using empty database.")
        return {}

players_db = load_players_db()
guess_counter = {}

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

@app.route('/api/players', methods=['GET'])
def get_players():
    """Return list of all player names"""
    return jsonify(list(players_db.keys()))

@app.route('/api/player_awards', methods=['GET'])
def get_player_awards():
    """Return list of all player names (for compatibility with frontend)"""
    return jsonify(list(players_db.keys()))

@app.route('/api/guess', methods=['POST'])
def guess():
    data = request.json
    guess_input = data['guess']
    target_input = data['target']

    guess_player, guess_key = get_player(guess_input)
    target_player, target_key = get_player(target_input)

    if not guess_player or not target_player:
        return jsonify({"error": "Invalid player name."}), 400

    guess_counter[target_key] = guess_counter.get(target_key, 0) + 1

    if guess_key == target_key:
        similarities = []
        for other_name, other_data in players_db.items():
            if other_name == target_key:
                continue
            sim_score, _ = compute_similarity(other_data, target_player, other_name, target_key)
            similarities.append((other_name, sim_score))
        top_5 = sorted(similarities, key=lambda x: x[1], reverse=True)[:5]

        return jsonify({
            "score": 100,
            "message": "🔥 You got it!",
            "matched_name": guess_key,
            "top_5": top_5
        })

    score, breakdown = compute_similarity(guess_player, target_player, guess_key, target_key)

    return jsonify({
        "score": score,
        "matched_name": guess_key,
        "breakdown": breakdown
    })

if __name__ == '__main__':
    print("Starting NBA Similarity Game Backend...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
