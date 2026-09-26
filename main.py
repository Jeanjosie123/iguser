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

# DomScan คิด 2 credits / username
BATCH = 5

# 70% เป็น 3L / 30% เป็น 4L
THREE_LETTER_RATIO = 0.70


# ==========================================
# GENERATE USERNAMES
# ==========================================

def generate_username():
    length = 3 if random.random() < THREE_LETTER_RATIO else 4

    # 75% ตัวอักษรล้วน
    if random.random() < 0.75:
        chars = string.ascii_lowercase
    else:
        chars = string.ascii_lowercase + string.digits

    while True:
        username = "".join(
            random.choice(chars)
            for _ in range(length)
        )

        # ต้องมีตัวอักษรอย่างน้อย 1 ตัว
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
            print("DomScan timeout.")

            if attempt < 2:
                time.sleep(5)

        except requests.exceptions.RequestException as e:
            print("DomScan request failed:", e)
            return None

        except ValueError:
            print("DomScan returned invalid JSON.")
            return None

    return None


def extract_results(data):
    if data is None:
        return []

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in (
        "results",
        "items",
        "data",
        "handles",
    ):
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
                "confidence": confidence
            })

    return passed


# ==========================================
# LAYER 2 — INSTAGRAM PUBLIC PROFILE
# ==========================================

def verify_instagram(username):
    url = f"https://www.instagram.com/{username}/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
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
            f"HTTP={status} "
            f"final={final_url}"
        )

        # โปรไฟล์มีอยู่
        if status == 200:
            return False, "profile_exists_or_uncertain"

        # ไม่มี public profile ที่ URL นี้
        if status == 404:
            return True, "public_profile_not_found"

        # Instagram จำกัด request
        if status == 429:
            return False, "rate_limited"

        # ถ้าโดนพาไป login/challenge
        # เราไม่ถือว่าผ่าน
        if (
            "/accounts/login" in final_url
            or "/challenge" in final_url
        ):
            return False, "instagram_blocked_check"

        # response อื่น ๆ = ไม่ชัดเจน
        return False, f"uncertain_http_{status}"

    except requests.exceptions.Timeout:
        return False, "timeout"

    except requests.exceptions.RequestException:
        return False, "request_error"


def second_layer_check(candidates):
    verified = []

    print()
    print("=" * 50)
    print("LAYER 2: INSTAGRAM")
    print("=" * 50)

    for candidate in candidates:
        username = candidate["username"]

        passed, reason = verify_instagram(username)

        print(
            f"@{username} -> "
            f"{'PASS' if passed else 'REJECT'} "
            f"({reason})"
        )

        if passed:
            candidate["verification"] = reason
            verified.append(candidate)

        # ไม่ยิงติดกัน
        time.sleep(2)

    return verified


# ==========================================
# DISCORD
# ==========================================

def send_discord(results):
    if not results:
        print()
        print("No username passed both checks.")
        print("Discord notification skipped.")
        return

    lines = []

    for result in results:
        username = result["username"]
        confidence = result.get("confidence") or "unknown"

        lines.append(
            f"✅ **@{username}** · {len(username)}L\n"
            f"DomScan: AVAILABLE\n"
            f"DomScan confidence: {confidence}\n"
            f"Instagram public profile: NOT FOUND\n"
            f"<https://www.instagram.com/{username}/>"
        )

    message = (
        "## ✅ DOUBLE-CHECKED IG USERNAMES\n\n"
        + "\n\n".join(lines)
        + "\n\n"
        + "Passed DomScan + Instagram public-profile check."
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

        print("Discord notification sent.")

    except requests.exceptions.RequestException as e:
        print("Discord error:", e)


# ==========================================
# MAIN
# ==========================================

def main():
    print("=" * 50)
    print("IG USERNAME FINDER — DOUBLE CHECK")
    print("=" * 50)

    usernames = generate_batch(BATCH)

    print()
    print("Generated usernames:")

    for username in usernames:
        print(" -", username)

    # --------------------------
    # CHECK 1
    # --------------------------

    domscan_data = check_domscan(usernames)

    if domscan_data is None:
        print("DomScan failed.")
        print("Ending round.")
        return

    candidates = get_domscan_available(domscan_data)

    print()
    print(
        "Passed DomScan:",
        len(candidates)
    )

    if not candidates:
        print("Nothing passed DomScan.")
        return

    # --------------------------
    # CHECK 2
    # --------------------------

    verified = second_layer_check(candidates)

    print()
    print(
        "Passed BOTH checks:",
        len(verified)
    )

    for item in verified:
        print(
            "DOUBLE CHECK PASSED:",
            item["username"]
        )

    # --------------------------
    # DISCORD
    # --------------------------

    send_discord(verified)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
