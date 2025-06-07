import json

def fix_name_encoding(bad_name):
    try:
        return bad_name.encode('latin1').decode('utf-8')
    except UnicodeDecodeError:
        return bad_name  # leave unchanged if decode fails

# Step 1: Load the original JSON file
with open("players.json", "r", encoding="utf-8") as f:
    players = json.load(f)

# Step 2: Fix any badly encoded player names
fixed_players = {}
renamed_count = 0
for name, data in players.items():
    fixed_name = fix_name_encoding(name)
    if fixed_name != name:
        renamed_count += 1
    fixed_players[fixed_name] = data

# Step 3: Remove any season with team == "TOT"
updated_count = 0
for player_name, data in fixed_players.items():
    if "seasons" in data:
        original_len = len(data["seasons"])
        data["seasons"] = [s for s in data["seasons"] if s.get("team") != "TOT"]
        cleaned_len = len(data["seasons"])
        if original_len != cleaned_len:
            print(f"{player_name}: removed {original_len - cleaned_len} 'TOT' season(s)")
            updated_count += 1

# Step 4: Save the cleaned data to a new file
with open("players_cleaned.json", "w", encoding="utf-8") as f:
    json.dump(fixed_players, f, indent=2, ensure_ascii=False)  # ensure_ascii=False preserves characters like č

print(f"\n✅ Finished cleaning.")
print(f" - {renamed_count} player names were fixed.")
print(f" - {updated_count} players had 'TOT' seasons removed.\n")

# Step 5: Confirm one player
player_check = "Luka Dončić"  # now correctly spelled
if player_check in fixed_players:
    print(f"{player_check}'s seasons (after cleaning):")
    for season in fixed_players[player_check]["seasons"]:
        print(f"  - {season['season']} with {season['team']}")
else:
    print(f"{player_check} not found in player list.")
