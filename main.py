import os
import random
import string
import requests

WEBHOOK = os.environ["DISCORD_WEBHOOK"]

LETTERS = string.ascii_lowercase
DIGITS = string.digits


def generate():
    # 75% เป็น 3 ตัว / 25% เป็น 4 ตัว
    length = 3 if random.random() < 0.75 else 4

    # เน้นตัวอักษรล้วน แต่มีแบบผสมเลขบ้าง
    if random.random() < 0.70:
        return "".join(random.choice(LETTERS) for _ in range(length))

    chars = LETTERS + DIGITS
    name = "".join(random.choice(chars) for _ in range(length))

    # ต้องมีตัวอักษรอย่างน้อยหนึ่งตัว
    if not any(c.isalpha() for c in name):
        return generate()

    return name


def send_discord(usernames):
    lines = []

    for username in usernames:
        profile = f"https://www.instagram.com/{username}/"
        lines.append(
            f"🔎 **@{username}** · {len(username)}L\n"
            f"<{profile}>"
        )

    message = (
        "## IG USERNAME CANDIDATES\n"
        f"Generated `{len(usernames)}` names\n\n"
        + "\n\n".join(lines)
        + "\n\n⚠️ Candidate list — verify availability inside Instagram."
    )

    r = requests.post(
        WEBHOOK,
        json={"content": message},
        timeout=20
    )

    print("Discord status:", r.status_code)

    if r.status_code not in (200, 204):
        print("Discord response:", r.text)
        r.raise_for_status()


def main():
    amount = int(os.getenv("BATCH", "20"))

    generated = set()

    while len(generated) < amount:
        generated.add(generate())

    usernames = sorted(generated)

    print(f"Generated {len(usernames)} candidates")

    for username in usernames:
        print("CANDIDATE:", username)

    # ส่ง Discord แค่ครั้งเดียวต่อรอบ
    send_discord(usernames)

    print("Done.")


if __name__ == "__main__":
    main()
