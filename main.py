import os
import random
import string
import requests

WEBHOOK = os.environ["DISCORD_WEBHOOK"]

# เน้น 3L ก่อน เพราะหายากกว่า
THREE_RATIO = 0.75

# ตัวอักษรที่อ่านง่าย
LETTERS = string.ascii_lowercase
DIGITS = string.digits

def generate():
    length = 3 if random.random() < THREE_RATIO else 4

    # สุ่มหลายรูปแบบ
    mode = random.choice(["letters", "letters", "mixed"])

    if mode == "letters":
        return "".join(random.choice(LETTERS) for _ in range(length))

    chars = LETTERS + DIGITS
    name = "".join(random.choice(chars) for _ in range(length))

    # ต้องมีตัวอักษรอย่างน้อย 1 ตัว
    if not any(c.isalpha() for c in name):
        return generate()

    return name


def send_discord(username):
    profile = f"https://www.instagram.com/{username}/"

    data = {
        "content": (
            "🔎 **NEW IG CANDIDATE**\n\n"
            f"**@{username}**\n"
            f"Length: `{len(username)}`\n"
            f"Profile: <{profile}>\n\n"
            "⚠️ Candidate only — confirm availability inside Instagram."
        )
    }

    r = requests.post(WEBHOOK, json=data, timeout=15)
    r.raise_for_status()


def main():
    amount = int(os.getenv("BATCH", "20"))

    generated = set()

    while len(generated) < amount:
        generated.add(generate())

    print(f"Generated {len(generated)} candidates")

    for username in sorted(generated):
        print("CANDIDATE:", username)
        send_discord(username)


if __name__ == "__main__":
    main()
