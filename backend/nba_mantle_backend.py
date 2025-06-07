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
        with open('players_cleaned.json', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: players_cleaned.json not found. Using empty database.")
        return {}

players_db = load_players_db()
guess_counter = {}

def compute_similarity(player1, player2, name1=None, name2=None):
    score = 0
    breakdown = {}

    p1_seasons = set((s["team"], s["season"]) for s in player1.get("seasons", []))
    p2_seasons = set((s["team"], s["season"]) for s in player2.get("seasons", []))
    shared_seasons = sorted(p1_seasons & p2_seasons, key=lambda x: x[1])
    shared_season_count = len(shared_seasons)

    consecutive_bonus = 0
    if shared_season_count >= 2:
        seasons_only = [season for _, season in shared_seasons]
        streak = 1
        max_streak = 1
        for i in range(1, len(seasons_only)):
            if seasons_only[i] == seasons_only[i-1] + 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        consecutive_bonus = max_streak * 2

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
    breakdown["shared_seasons_detail"] = shared_seasons

    teammate_years = player1.get("teammate_years", {}).get(name2, 0)
    if teammate_years >= 6:
        pts = 15
    elif teammate_years >= 4:
        pts = 10
    elif teammate_years >= 3:
        pts = 7
    elif teammate_years == 2:
        pts = 4
    elif teammate_years == 1:
        pts = 1
    else:
        pts = 0
    score += pts
    breakdown["teammate_years"] = pts

    overlap_teams = set(player1.get("teams", [])) & set(player2.get("teams", []))
    overlap = len(overlap_teams)
    pts = min(overlap * 3, 9)
    score += pts
    breakdown["franchise_overlap"] = pts

    tenure_bonus = 0
    for team in overlap_teams:
        p1_years = {s["season"] for s in player1.get("seasons", []) if s["team"] == team}
        p2_years = {s["season"] for s in player2.get("seasons", []) if s["team"] == team}
        common_years = p1_years & p2_years
        if len(common_years) >= 3:
            tenure_bonus += 3
        elif len(common_years) == 2:
            tenure_bonus += 2
        elif len(common_years) == 1:
            tenure_bonus += 1
    score += tenure_bonus
    breakdown["franchise_tenure_bonus"] = tenure_bonus

    if player1.get("archetype") == player2.get("archetype"):
        pts = 8
    else:
        pairs = {("Guard", "Wing"), ("Wing", "Big"), ("Guard", "Big")}
        a1 = player1.get("archetype", "")
        a2 = player2.get("archetype", "")
        pts = 2 if (a1, a2) in pairs or (a2, a1) in pairs else 0
    score += pts
    breakdown["archetype"] = pts

    if player1.get("position") == player2.get("position"):
        pts = 6
    elif player1.get("position", "")[:2] == player2.get("position", "")[:2]:
        pts = 2
    else:
        pts = 0
    score += pts
    breakdown["position"] = pts

    draft_diff = abs(player1.get("draft_year", 0) - player2.get("draft_year", 0))
    if draft_diff <= 1:
        pts = 3
    elif draft_diff <= 3:
        pts = 2
    else:
        pts = 0
    score += pts
    breakdown["draft_diff"] = pts

    era_diff = abs(player1.get("start_year", 0) - player2.get("start_year", 0))
    if era_diff <= 5:
        pts = 5
    elif era_diff <= 10:
        pts = 2
    else:
        pts = 0
    score += pts
    breakdown["era_diff"] = pts

    p1_end = player1.get("start_year", 0) + player1.get("career_length", 0)
    p2_end = player2.get("start_year", 0) + player2.get("career_length", 0)
    end_diff = abs(p1_end - p2_end)
    end_bonus = 2 if end_diff <= 3 else 0
    score += end_bonus
    breakdown["career_end_proximity"] = end_bonus

    cl_diff = abs(player1.get("career_length", 0) - player2.get("career_length", 0))
    if cl_diff <= 3:
        pts = 2
    elif cl_diff <= 5:
        pts = 1
    else:
        pts = 0
    score += pts
    breakdown["career_length"] = pts

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