import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import requests

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "vivek.zapier@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "lmkx unfr qjgz monb")
RECIPIENT_EMAIL = "vivek.zapier@gmail.com"
JSON_FILE_PATH = "kalshi_markets.json"

# Fetch data
def pull_kalshi_data():
    url = "https://api.elections.kalshi.com/trade-api/v2/markets"
    headers = {"accept": "application/json"}
    params = {"status": "open"}
    kalshi_markets = []
    cursor = None
    call_count = 0
    for _ in range(1500):
        if cursor:
            params["cursor"] = cursor
        response = requests.get(url, headers=headers, params=params)
        call_count += 1
        data = response.json()
        kalshi_markets.extend(data.get("markets", []))
        cursor = data.get("cursor")
        if not cursor:
            break
    with open("kalshi_markets.json", "w", encoding="utf-8") as file:
        json.dump({"markets": kalshi_markets}, file, indent=4)
    print(f"Total API calls made: {call_count}")


def check_and_send_email(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            markets = data.get("markets", [])
            for market in markets:
                ticker = market.get("ticker", "")
                yes_ask = market.get("yes_ask")
                if "KXSPOTIFYARTISTD" in ticker and "DRA" in ticker and isinstance(yes_ask, (int, float)) and yes_ask < 100:
                    subject = "Kalshi Market Alert: DRA Spotify Contract Below 70"
                    body = f"The Kalshi market with ticker '{ticker}' has a yes_ask price of {yes_ask}, which is below 70."
                    send_email(subject, body)
                    print(f"Alert email sent for {ticker}")
                    return  # Send only one email if multiple contracts match for now
            print("No matching contracts found with yes_ask below 70.")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    # Extract Kalshi data
    pull_kalshi_data()
    check_and_send_email(JSON_FILE_PATH)
