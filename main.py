import os
import random
import string
import time
import requests

WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

if not WEBHOOK:
    raise RuntimeError("Missing DISCORD_WEBHOOK secret")

# ===== SETTINGS =====
LENGTHS = [3, 4]
DELAY_MIN = 8
DELAY_MAX = 15
CHECKED_FILE = "checked.txt"
CHARS = string.ascii_lowercase + string.digits

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
    )
})

def load_checked():
    try:
        with open(CHECKED_FILE, "r", encoding="utf-8") as f:
            return set(x.strip() for x in f if x.strip())
    except FileNotFoundError:
        return set()

def save_checked(username):
    with open(CHECKED_FILE, "a", encoding="utf-8") as f:
        f.write(username + "\n")

def generate_username():
    length = random.choice(LENGTHS)
    return "".join(random.choice(CHARS) for _ in range(length))

def check_username(username):
    url = f"https://www.instagram.com/{username}/"
    try:
        r = session.get(url, timeout=10, allow_redirects=False)
        if r.status_code == 404:
            return "LIKELY_AVAILABLE"
        if r.status_code == 200:
            return "TAKEN"
        if r.status_code == 429:
            return "RATE_LIMIT"
        return "UNKNOWN"
    except requests.RequestException:
        return "ERROR"

def send_discord(username):
    payload = {
        "content": (
            "🔎 **IG Username Candidate**\n"
            f"Username: `{username}`\n"
            f"https://www.instagram.com/{username}/\n"
            "Status: 🟢 **LIKELY AVAILABLE**\n"
            "⚠️ Confirm availability inside Instagram before claiming."
        )
    }
    try:
        r = requests.post(WEBHOOK, json=payload, timeout=10)
        if not r.ok:
            print("Discord error:", r.status_code)
    except requests.RequestException as e:
        print("Discord connection error:", e)

def main():
    checked = load_checked()
    total = 0
    found = 0

    print("=" * 40)
    print("IG 3L / 4L Username Finder")
    print("=" * 40)

    while True:
        username = generate_username()
        if username in checked:
            continue

        checked.add(username)
        save_checked(username)
        total += 1
        print(f"[{total}] Checking @{username}...", end=" ", flush=True)

        result = check_username(username)

        if result == "LIKELY_AVAILABLE":
            found += 1
            print("LIKELY AVAILABLE ✓")
            send_discord(username)
            print(f"     → Discord sent | Candidates: {found}")
        elif result == "TAKEN":
            print("TAKEN")
        elif result == "RATE_LIMIT":
            print("RATE LIMITED")
            print("Waiting 5 minutes...")
            time.sleep(300)
        elif result == "ERROR":
            print("NETWORK ERROR")
            time.sleep(30)
        else:
            print("UNKNOWN")

        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

if __name__ == "__main__":
    main()
