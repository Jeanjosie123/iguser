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

# จำนวนชื่อต่อรอบ
BATCH = 5

# 10% = 3 ตัว / 90% = 4 ตัว
THREE_LETTER_RATIO = 0.10


# ==========================================
# GENERATOR
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
# DOMSCAN
# ==========================================

def check_domscan(usernames):
    headers = {
        "Authorization": f"Bearer {DOMSCAN_API_KEY}",
        "X-API-Key": DOMSCAN_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # ตรวจ Instagram อย่างเดียว
    payload = {
        "handles": usernames,
        "platforms": ["instagram"]
    }

    print()
    print("=" * 50)
    print("DOMSCAN INSTAGRAM CHECK")
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
            print("DomScan request error:", e)
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


# ==========================================
# FILTER
# ==========================================

def find_candidates(data):
    results = extract_results(data)

    candidates = []

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
        method = instagram.get("method")
        cached = instagram.get("cached")

        print(
            f"@{username} | "
            f"available={available} | "
            f"checked={checked} | "
            f"confidence={confidence} | "
            f"method={method} | "
            f"cached={cached}"
        )

        # รับเฉพาะ DomScan ที่ตรวจสำเร็จและบอกว่าว่าง
        if (
            username
            and checked is True
            and available is True
        ):
            candidates.append({
                "username": username,
                "confidence": confidence or "unknown",
                "method": method or "unknown",
                "cached": cached
            })

    return candidates


# ==========================================
# DISCORD
# ==========================================

def send_discord(candidates):
    if not candidates:
        print()
        print("No available candidates.")
        print("Discord skipped.")
        return

    lines = []

    for item in candidates:
        username = item["username"]
        confidence = item["confidence"]
        method = item["method"]
        cached = item["cached"]

        cache_text = (
            "yes" if cached is True
            else "no" if cached is False
            else "unknown"
        )

        lines.append(
            f"🔎 **@{username}** · {len(username)}L\n"
            f"DomScan: AVAILABLE\n"
            f"Confidence: {confidence}\n"
            f"Method: {method}\n"
            f"Cached: {cache_text}\n"
            f"<https://www.instagram.com/{username}/>"
        )

    message = (
        "## 🔎 IG USERNAME CANDIDATES\n\n"
        + "\n\n".join(lines)
        + "\n\n"
        + "ผ่าน DomScan: checked=true + available=true\n"
        + "สถานะนี้เป็น candidate ไม่ใช่การยืนยันว่า Instagram จะอนุญาตให้ claim"
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

    data = check_domscan(usernames)

    if data is None:
        print("DomScan failed.")
        return

    candidates = find_candidates(data)

    print()
    print("Available candidates:", len(candidates))

    for item in candidates:
        print("CANDIDATE:", item["username"])

    send_discord(candidates)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
