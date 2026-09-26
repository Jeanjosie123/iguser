import os
import random
import string
import time
import requests

# =========================
# CONFIG
# =========================

DOMSCAN_API_KEY = os.environ["DOMSCAN_API_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

DOMSCAN_URL = "https://domscan.net/v1/social/bulk"

# DomScan = 2 credits / username
# เริ่มน้อยก่อนเพื่อไม่ให้ bulk timeout
BATCH = 5

# สัดส่วน 3L / 4L
THREE_LETTER_RATIO = 0.70


# =========================
# USERNAME GENERATOR
# =========================

def generate_username():
    length = 3 if random.random() < THREE_LETTER_RATIO else 4

    # ส่วนใหญ่เป็นตัวอักษรล้วน
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


# =========================
# DOMSCAN
# =========================

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
    print("Sending to DomScan...")
    print("Handles:", usernames)

    # ลองใหม่ได้ 2 ครั้ง ถ้า server ช้า
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

            data = response.json()

            print("DomScan response received.")

            return data

        except requests.exceptions.Timeout:
            print("DomScan timeout.")

            if attempt < 2:
                print("Waiting 5 seconds before retry...")
                time.sleep(5)

        except requests.exceptions.HTTPError as e:
            print("DomScan HTTP error:", e)

            try:
                print("Response:", response.text[:1000])
            except Exception:
                pass

            return None

        except requests.exceptions.RequestException as e:
            print("DomScan connection error:", e)
            return None

        except ValueError:
            print("DomScan returned invalid JSON.")
            return None

    print("DomScan did not respond after retries.")
    return None


# =========================
# PARSE BULK RESPONSE
# =========================

def extract_results(data):
    if data is None:
        return []

    # API อาจคืน list โดยตรง
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    # รองรับชื่อ field ที่ bulk API อาจใช้
    for key in (
        "results",
        "items",
        "data",
        "handles",
    ):
        value = data.get(key)

        if isinstance(value, list):
            return value

    # เผื่อ API คืน single result
    if "handle" in data and "availability" in data:
        return [data]

    return []


def find_available(data):
    results = extract_results(data)

    print()
    print("Results returned:", len(results))

    available_usernames = []

    for item in results:
        if not isinstance(item, dict):
            continue

        username = item.get("handle")

        availability = item.get("availability", {})

        if not isinstance(availability, dict):
            continue

        instagram = availability.get("instagram", {})

        if not isinstance(instagram, dict):
            continue

        available = instagram.get("available")
        checked = instagram.get("checked")
        confidence = instagram.get("confidence")
        cached = instagram.get("cached")
        method = instagram.get("method")

        print(
            f"@{username} | "
            f"available={available} | "
            f"checked={checked} | "
            f"confidence={confidence} | "
            f"cached={cached} | "
            f"method={method}"
        )

        # ส่งเฉพาะชื่อที่ DomScan ระบุว่า
        # ตรวจแล้ว + available จริง
        if (
            username
            and checked is True
            and available is True
        ):
            available_usernames.append({
                "username": username,
                "confidence": confidence,
                "cached": cached,
                "method": method,
            })

    return available_usernames


# =========================
# DISCORD
# =========================

def send_discord(results):
    if not results:
        print()
        print("No available Instagram usernames found.")
        print("Nothing will be sent to Discord.")
        return

    lines = []

    for result in results:
        username = result["username"]
        confidence = result.get("confidence") or "unknown"

        lines.append(
            f"✅ **@{username}** · {len(username)}L\n"
            f"DomScan: AVAILABLE\n"
            f"Confidence: {confidence}\n"
            f"<https://www.instagram.com/{username}/>"
        )

    message = (
        "## ✅ AVAILABLE IG USERNAMES\n\n"
        + "\n\n".join(lines)
        + "\n\n"
        + "ตรวจโดย DomScan ก่อนส่งข้อความนี้"
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
        # Discord มีปัญหาไม่ควรทำให้ตัวค้นหาทั้งรอบพัง
        print("Discord send failed:", e)


# =========================
# MAIN
# =========================

def main():
    print("=" * 45)
    print("IG USERNAME FINDER")
    print("=" * 45)

    usernames = generate_batch(BATCH)

    print()
    print(f"Generated {len(usernames)} usernames:")

    for username in usernames:
        print(" -", username)

    data = check_domscan(usernames)

    if data is None:
        print()
        print("DomScan check failed.")
        print("Ending this round without Discord notification.")
        return

    available = find_available(data)

    print()
    print("Available found:", len(available))

    for result in available:
        print("AVAILABLE:", result["username"])

    send_discord(available)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
