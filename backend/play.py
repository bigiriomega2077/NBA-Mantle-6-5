import requests
import json
import random
import os

def get_top_5(target_name):
    payload = {"guess": target_name, "target": target_name}
    response = requests.post("http://127.0.0.1:5000/guess", json=payload)
    if response.ok:
        result = response.json()
        return result.get("top_5", [])
    return []

# Load cleaned players
with open("players_cleaned.json", encoding="utf-8") as f:
    players_data = json.load(f)

# Filter: modern players only (post-2010, 6+ seasons)
modern_players = [
    name for name, info in players_data.items()
    if info.get("start_year", 0) >= 2003 and info.get("career_length", 0) >= 5
]

def play_game():
    target = random.choice(modern_players)
    #target = "Serge Ibaka"
    guess_count = 0
    history = []

    print("\n🧠 NBA Similarity Guessing Game!\nGuess the mystery player.")
    print("Type 'reveal' to show the answer or 'quit' to exit.\n")

    while True:
        guess = input("🔍 Your guess: ").strip()
        if guess.lower() == "quit":
            print(f"\n👋 Thanks for playing. The correct player was: {target}\n")
            break
        if guess.lower() == "reveal":
            print(f"\n🎯 The answer was: {target}\n")
            top_5 = get_top_5(target)
            if top_5:
                print("🏀 Top 5 Closest Players:")
                for name, score in top_5:
                    print(f"   {name:<25} → {score}/100")
            break

        guess_count += 1
        payload = {"guess": guess, "target": target}

        try:
            response = requests.post("http://127.0.0.1:5000/guess", json=payload)
            if response.ok:
                result = response.json()
                score = result["score"]
                top_5 = result.get("top_5", [])
                message = result.get("message", "")
                hint = result.get("hint", "")

                matched_name = result.get("matched_name", guess)
                history.append((matched_name, score))
                history_sorted = sorted(history, key=lambda x: x[1], reverse=True)[:10]

                os.system("cls" if os.name == "nt" else "clear")

                print(f"🧠 NBA Similarity Guessing Game - Attempt #{guess_count}")
                print("-" * 40)
                print(f"🔁 Most Recent Guess: {matched_name:<25} → {score}/100")
                print("-" * 40)
                print("📜 Guess History (Sorted by Score):")
                for g, s in history_sorted:
                    print(f"   {g:<25} → {s}/100")
                print("-" * 40)

                if message:
                    print(f"🎯 {message}")

                if top_5:
                    print("\n🏀 Top 5 Closest Players:")
                    for name, sim in top_5:
                        print(f"   {name:<25} → {sim}/100")

                if hint:
                    print(f"\n💡 Hint: {hint}")

                if score == 100:
                    print(f"\n🔥 You got it! The answer was {target} in {guess_count} guesses.\n")
                    break
            else:
                error_msg = response.json().get("error", "Unknown error.")
                print(f"❌ {error_msg}\n")
        except Exception as e:
            print("⚠️ Connection error. Make sure the Flask server is running on http://127.0.0.1:5000")
            break

# 🔁 Main loop to allow replay
while True:
    play_game()
    again = input("\n🔁 Play again? (y/n): ").strip().lower()
    if again != "y":
        print("\n👋 Thanks for playing!\n")
        break
