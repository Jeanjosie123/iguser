import os
import random
import string
import time
import requests

# ==========================================
# CONFIG
# ==========================================

DOMSCAN_API_KEY = os.environ["DOMSCAN_API_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

DOMSCAN_URL = "https://domscan.net/v1/social/bulk"

BATCH = 5

# 10% = 3 ตัว / 90% = 4 ตัว
THREE_LETTER_RATIO = 0.10


# ==========================================
# GENERATOR
# ==========================================

def generate_username():
    length = 3 if random.random() < THREE_LETTER_RATIO else 4

    # ส่วนใหญ่เป็นตัวอักษร
    if random.random() < 0.75:
        chars = string.ascii_lowercase
    else:
        chars = string.ascii_lowercase + string.digits

    while True:
        username = "".join(
            random.choice(chars)
            for _ in range(length)
        )

        if any(c.isalpha() for c in username):
            return username


def generate_batch(amount):
    usernames = set()

    while len(usernames) < amount:
        usernames.add(generate_username())

    return list(usernames)


# ==========================================
# LAYER 1 — DOMSCAN
# ==========================================

def check_domscan(usernames):
    headers = {
        "Authorization": f"Bearer {DOMSCAN_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "handles": usernames
    }

    print()
    print("=" * 50)
    print("LAYER 1: DOMSCAN")
    print("=" * 50)

    for attempt in range(1, 3):
        try:
            print(f"DomScan attempt {attempt}/2")

            response = requests.post(
                DOMSCAN_URL,
                headers=headers,
                json=payload,
                timeout=(15, 120)
            )

            print("DomScan HTTP:", response.status_code)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            print("DomScan timeout")

            if attempt < 2:
                time.sleep(5)

        except requests.exceptions.RequestException as e:
            print("DomScan error:", e)
            return None

        except ValueError:
            print("DomScan returned invalid JSON")
            return None

    return None


def extract_results(data):
    if data is None:
        return []

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in ("results", "items", "data", "handles"):
        value = data.get(key)

        if isinstance(value, list):
            return value

    if "handle" in data and "availability" in data:
        return [data]

    return []


def get_domscan_available(data):
    results = extract_results(data)

    passed = []

    print()
    print("DomScan results:", len(results))

    for item in results:
        if not isinstance(item, dict):
            continue

        username = item.get("handle")

        instagram = (
            item.get("availability", {})
            .get("instagram", {})
        )

        if not isinstance(instagram, dict):
            continue

        available = instagram.get("available")
        checked = instagram.get("checked")
        confidence = instagram.get("confidence")

        print(
            f"@{username} | "
            f"available={available} | "
            f"checked={checked} | "
            f"confidence={confidence}"
        )

        if (
            username
            and checked is True
            and available is True
        ):
            passed.append({
                "username": username,
                "confidence": confidence or "unknown"
            })

    return passed


# ==========================================
# LAYER 2 — PUBLIC INSTAGRAM CHECK
# ==========================================

def check_instagram_public(username):
    url = f"https://www.instagram.com/{username}/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=20,
            allow_redirects=True
        )

        status = response.status_code
        final_url = response.url.lower()

        print(
            f"Instagram @{username}: "
            f"HTTP={status} final={final_url}"
        )

        # GitHub Actions มักถูก Instagram ส่งมาหน้า login
        # อันนี้ไม่ได้บอกว่าชื่อถูกใช้
        if (
            "/accounts/login" in final_url
            or "/challenge" in final_url
        ):
            return "INCONCLUSIVE", "login_redirect"

        # พบหน้า profile
        if status == 200:
            return "TAKEN_OR_UNCERTAIN", "public_page_returned_200"

        # ไม่พบ public profile
        if status == 404:
            return "NO_PUBLIC_PROFILE", "http_404"

        if status == 429:
            return "INCONCLUSIVE", "rate_limited"

        return "INCONCLUSIVE", f"http_{status}"

    except requests.exceptions.Timeout:
        return "INCONCLUSIVE", "timeout"

    except requests.exceptions.RequestException:
        return "INCONCLUSIVE", "request_error"


def run_second_layer(candidates):
    results = []

    print()
    print("=" * 50)
    print("LAYER 2: INSTAGRAM PUBLIC CHECK")
    print("=" * 50)

    for candidate in candidates:
        username = candidate["username"]

        status, reason = check_instagram_public(username)

        candidate["instagram_status"] = status
        candidate["instagram_reason"] = reason

        print(
            f"@{username} -> "
            f"{status} ({reason})"
        )

        results.append(candidate)

        time.sleep(2)

    return results


# ==========================================
# DISCORD
# ==========================================

def send_discord(results):
    if not results:
        print()
        print("No DomScan available usernames.")
        print("Discord skipped.")
        return

    lines = []

    for result in results:
        username = result["username"]
        confidence = result["confidence"]
        ig_status = result["instagram_status"]

        if ig_status == "NO_PUBLIC_PROFILE":
            icon = "🟢"
            check_text = "No public profile found"
        elif ig_status == "INCONCLUSIVE":
            icon = "🟡"
            check_text = "Public check inconclusive"
        else:
            # DomScan บอกว่าว่าง แต่ public check ขัดแย้ง
            # ไม่ส่งชื่อนี้
            print(
                f"Skipping @{username}: "
                f"public check conflicts with DomScan"
            )
            continue

        lines.append(
            f"{icon} **@{username}** · {len(username)}L\n"
            f"DomScan: AVAILABLE\n"
            f"Confidence: {confidence}\n"
            f"Instagram check: {check_text}\n"
            f"<https://www.instagram.com/{username}/>"
        )

    if not lines:
        print()
        print("Nothing safe enough to send.")
        return

    message = (
        "## IG USERNAME CANDIDATES\n\n"
        + "\n\n".join(lines)
        + "\n\n"
        + "🟢 = no public profile found\n"
        + "🟡 = Instagram blocked/redirected the public check\n"
        + "Availability is not a guarantee that Instagram will allow the username to be claimed."
    )

    try:
        response = requests.post(
            DISCORD_WEBHOOK,
            json={
                "content": message,
                "allowed_mentions": {
                    "parse": []
                }
            },
            timeout=20
        )

        print()
        print("Discord HTTP:", response.status_code)

        response.raise_for_status()

        print("Discord sent.")

    except requests.exceptions.RequestException as e:
        print("Discord error:", e)


# ==========================================
# MAIN
# ==========================================

def main():
    print("=" * 50)
    print("IG USERNAME FINDER")
    print("=" * 50)

    usernames = generate_batch(BATCH)

    print()
    print("Generated usernames:")

    for username in usernames:
        print(" -", username)

    domscan_data = check_domscan(usernames)

    if domscan_data is None:
        print("DomScan failed.")
        return

    candidates = get_domscan_available(domscan_data)

    print()
    print("Passed DomScan:", len(candidates))

    if not candidates:
        print("Nothing passed DomScan.")
        return

    results = run_second_layer(candidates)

    print()
    print("Candidates processed:", len(results))

    send_discord(results)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
