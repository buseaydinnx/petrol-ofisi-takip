import json
import os
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TRACKS = [
    {
        "name": "Bursa / Karacabey",
        "url": "https://www.petrolofisi.com.tr/akaryakit-fiyatlari/bursa-akaryakit-fiyatlari",
        "district": "KARACABEY",
    },
    {
        "name": "Aksaray / Aksaray",
        "url": "https://www.petrolofisi.com.tr/akaryakit-fiyatlari/aksaray-akaryakit-fiyatlari",
        "district": "AKSARAY",
    },
    {
        "name": "İzmir / Tire",
        "url": "https://www.petrolofisi.com.tr/akaryakit-fiyatlari/izmir-akaryakit-fiyatlari",
        "district": "TIRE",
    },
    {
        "name": "Bingöl / Bingöl",
        "url": "https://www.petrolofisi.com.tr/akaryakit-fiyatlari/bingol-akaryakit-fiyatlari",
        "district": "BINGOL",
    },
]

PRODUCT = "V/Max Diesel"
STATE_FILE = Path("data/last_prices.json")


def normalize(text):
    return (
        text.upper()
        .replace("İ", "I")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ş", "S")
        .replace("Ö", "O")
        .replace("Ç", "C")
    )


def fetch_text(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text("\n", strip=True)


def extract_vmax_diesel_price(page_text, district):
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    norm_lines = [normalize(line) for line in lines]
    target = normalize(district)

    for i, line in enumerate(norm_lines):
        if line == target:
            chunk = lines[i : i + 25]
            for j, item in enumerate(chunk):
                if item.strip() == PRODUCT:
                    for candidate in chunk[j + 1 : j + 5]:
                        match = re.search(r"(\d+[.,]\d+)", candidate)
                        if match:
                            return match.group(1).replace(",", ".")
    raise ValueError(f"{district} için V/Max Diesel fiyatı bulunamadı.")


def load_old():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_new(data):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def send_mail(changes, current):
    sender = os.environ["OUTLOOK_EMAIL"]
    password = os.environ["OUTLOOK_PASSWORD"]
    receiver = os.environ.get("TO_EMAIL", sender)

    body = ["Petrol Ofisi V/Max Diesel fiyat değişikliği tespit edildi.", ""]
    body.append(datetime.now().strftime("%d.%m.%Y %H:%M"))
    body.append("")

    for name, old_price, new_price in changes:
        body.append(f"{name}: {old_price} TL/LT → {new_price} TL/LT")

    body.append("")
    body.append("Güncel takip edilen fiyatlar:")
    for name, price in current.items():
        body.append(f"{name}: {price} TL/LT")

    msg = MIMEText("\n".join(body), "plain", "utf-8")
    msg["Subject"] = "Petrol Ofisi V/Max Diesel Fiyat Değişikliği"
    msg["From"] = sender
    msg["To"] = receiver

    with smtplib.SMTP("smtp-mail.outlook.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)


def main():
    current = {}

    for item in TRACKS:
        text = fetch_text(item["url"])
        price = extract_vmax_diesel_price(text, item["district"])
        current[item["name"]] = price

    old = load_old()
    changes = []

    for name, new_price in current.items():
        old_price = old.get(name)
        if old_price and old_price != new_price:
            changes.append((name, old_price, new_price))

    if changes:
        send_mail(changes, current)

    save_new(current)
    print("Kontrol tamamlandı.")
    print(json.dumps(current, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
