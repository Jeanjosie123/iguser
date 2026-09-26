import os, random, string, time, requests

WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
BATCH = int(os.environ.get("BATCH", "20"))
CHECKED_FILE = "checked.txt"
CHARS = string.ascii_lowercase + string.digits

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
})

def send(msg):
    if not WEBHOOK:
        return False
    try:
        return requests.post(WEBHOOK, json={"content": msg}, timeout=15).status_code in (200, 204)
    except requests.RequestException:
        return False

def load_checked():
    try:
        with open(CHECKED_FILE, encoding="utf-8") as f:
            return {x.strip() for x in f if x.strip()}
    except FileNotFoundError:
        return set()

def save_checked(names):
    with open(CHECKED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(names)) + ("\n" if names else ""))

def generate(checked):
    while True:
        n = random.choice((3, 4))
        u = "".join(random.choice(CHARS) for _ in range(n))
        if u not in checked:
            return u

def check(u):
    # Follow redirects so a normal Instagram redirect is not automatically
    # treated as availability. This remains a public-profile signal only.
    try:
        r = s.get(f"https://www.instagram.com/{u}/", timeout=20, allow_redirects=True)
    except requests.RequestException as e:
        return "ERROR", type(e).__name__

    if r.status_code == 404:
        return "CANDIDATE", "final HTTP 404"
    if r.status_code == 429:
        return "RATE_LIMIT", "HTTP 429"
    if r.status_code == 200:
        final = r.url.rstrip("/")
        # If Instagram lands on login/challenge/home rather than the requested
        # profile, the public request is inconclusive.
        if any(x in final for x in ("/accounts/login", "/challenge")):
            return "UNKNOWN", "Instagram login/challenge redirect"
        return "TAKEN_OR_UNKNOWN", "final HTTP 200"
    return "UNKNOWN", f"final HTTP {r.status_code}"

def main():
    checked = load_checked()
    candidates = 0
    print(f"Starting batch of {BATCH}")

    for i in range(BATCH):
        u = generate(checked)
        checked.add(u)
        status, detail = check(u)
        print(f"[{i+1}/{BATCH}] @{u} -> {status} ({detail})", flush=True)

        if status == "CANDIDATE":
            candidates += 1
            send(
                "🔎 **IG Username Candidate**\n"
                f"Username: `{u}`\n"
                f"https://www.instagram.com/{u}/\n"
                f"Signal: `{detail}`\n"
                "⚠️ Public-profile candidate only; confirm inside Instagram before claiming."
            )
        elif status == "RATE_LIMIT":
            print("Rate limited; ending this batch.", flush=True)
            break

        time.sleep(random.uniform(8, 14))

    save_checked(checked)
    print(f"Done. Candidates this batch: {candidates}")

if __name__ == "__main__":
    main()
