import json

# Step 1: Load the original JSON file
with open("players.json", "r", encoding="utf-8") as f:
    players = json.load(f)

# Step 2: Remove any season with team == "TOT"
updated_count = 0
for player_name, data in players.items():
    if "seasons" in data:
        original_len = len(data["seasons"])
        data["seasons"] = [s for s in data["seasons"] if s.get("team") != "TOT"]
        cleaned_len = len(data["seasons"])
        if original_len != cleaned_len:
            print(f"{player_name}: removed {original_len - cleaned_len} 'TOT' season(s)")
            updated_count += 1

# Step 3: Save the cleaned data to a new file
with open("players_cleaned.json", "w", encoding="utf-8") as f:
    json.dump(players, f, indent=2)

print(f"\n✅ Finished cleaning. {updated_count} players were updated.\n")

# Step 4: Print Rajon Rondo's seasons to confirm
player_check = "Marc Gasol"
if player_check in players:
    print(f"{player_check}'s seasons (after cleaning):")
    for season in players[player_check]["seasons"]:
        print(f"  - {season['season']} with {season['team']}")
else:
    print(f"{player_check} not found in player list.")