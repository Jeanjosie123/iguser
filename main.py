import os
import random
import string
import requests

DOMSCAN_API_KEY = os.environ["DOMSCAN_API_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

DOMSCAN_URL = "https://domscan.net/v1/social/bulk"

# เริ่ม 10 ชื่อต่อรอบ = 20 credits
BATCH = 10


def generate_username():
    # เน้น 3L แต่มี 4L ด้วย
    length = 3 if random.random() < 0.70 else 4

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

        # ต้องมีตัวอักษรอย่างน้อยหนึ่งตัว
        if any(c.isalpha() for c in username):
            return username


def generate_batch(amount):
    names = set()

    while len(names) < amount:
        names.add(generate_username())

    return list(names)


def check_domscan(usernames):
    headers = {
        "Authorization": f"Bearer {DOMSCAN_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "handles": usernames
    }

    response = requests.post(
        DOMSCAN_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    print("DomScan HTTP:", response.status_code)
    response.raise_for_status()

    return response.json()


def find_available(data):
    available = []

    # รองรับ response ที่คืน results/items เป็น list
    if isinstance(data, dict):
        results = (
            data.get("results")
            or data.get("items")
            or data.get("data")
            or []
        )
    elif isinstance(data, list):
        results = data
    else:
        results = []

    for item in results:
        if not isinstance(item, dict):
            continue

        username = item.get("handle")

        instagram = (
            item.get("availability", {})
            .get("instagram", {})
        )

        is_available = instagram.get("available")
        checked = instagram.get("checked")

        print(
            username,
            "available=",
            is_available,
            "checked=",
            checked
        )

        # ส่งเฉพาะผลที่ DomScan ตรวจแล้วและตอบ available จริง
        if (
            username
            and checked is True
            and is_available is True
        ):
            available.append(username)

    return available


def send_discord(usernames):
    if not usernames:
        print("No available usernames this round.")
        return

    lines = []

    for username in usernames:
        lines.append(
            f"✅ **@{username}** · {len(username)}L\n"
            f"<https://www.instagram.com/{username}/>"
        )

    message = (
        "## AVAILABLE IG USERNAMES\n\n"
        + "\n\n".join(lines)
        + "\n\n"
        "Checked by DomScan immediately before this notification."
    )

    response = requests.post(
        DISCORD_WEBHOOK,
        json={"content": message},
        timeout=20
    )

    print("Discord HTTP:", response.status_code)
    response.raise_for_status()


def main():
    usernames = generate_batch(BATCH)

    print("Checking:")
    for username in usernames:
        print(" -", username)

    data = check_domscan(usernames)

    available = find_available(data)

    print("Available found:", len(available))

    for username in available:
        print("AVAILABLE:", username)

    send_discord(available)

    print("Done.")


if __name__ == "__main__":
    main()
