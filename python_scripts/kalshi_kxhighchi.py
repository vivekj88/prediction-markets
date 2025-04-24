import json
import smtplib
from email.mime.text import MIMEText
import os
from datetime import datetime, date, timezone # Added timezone
import math
import requests
import re

# --- Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# Use environment variable for sender email, defaulting to the example
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "vivek.zapier@gmail.com")

# Use environment variable for password, with the specified try/except fallback
try:
    SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
except KeyError:
    # This indicates the SENDER_PASSWORD environment variable was not set
    SENDER_PASSWORD = "Secret not available!"
    print("Warning: SENDER_PASSWORD environment variable not set.")

# Use the specified recipient email
RECIPIENT_EMAIL = "vivek.zapier@gmail.com"

KALSHI_FILE_PATH = "kalshi_markets.json"

# --- Dynamically determine target date ---
# Get current date
# NOTE: The Mesowest API uses local time for the station (America/Chicago),
# and Kalshi tickers likely use US/Eastern or UTC for their dates.
# For simplicity, we'll use the script's current local date.
# If running this near midnight, consider using a specific timezone (e.g., pytz library).
current_date = datetime.now().date()

# Format for temperature API filtering (YYYY-MM-DD)
TARGET_DATE_TEMP_API_STR = current_date.strftime("%Y-%m-%d")
# Format for Kalshi Ticker filtering (DDMONYY, uppercase)
TARGET_DATE_TICKER_STR = current_date.strftime("%d%b%y").upper()

# API Endpoint for Chicago Temps (KMDW station) - Fetches last 72 hours
TEMP_API_URL = "https://api.mesowest.net/v2/stations/timeseries?STID=KMDW&showemptystations=1&units=temp%7CF,speed%7Cmph,english&recent=4320&token=d8c6aee36a994f90857925cea26934be&complete=1&obtimezone=local"

# --- Kalshi Data Fetch Function ---
def pull_kalshi_data():
    """ Fetches open Kalshi markets and saves them to kalshi_markets.json """
    print("Fetching latest Kalshi market data...")
    url = "https://api.elections.kalshi.com/trade-api/v2/markets"
    headers = {"accept": "application/json"}
    params = {"status": "open"}
    kalshi_markets = []
    cursor = None
    call_count = 0
    max_calls = 1500 # Safety limit
    try:
        for _ in range(max_calls):
            if cursor:
                params["cursor"] = cursor
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status() # Check for HTTP errors
            call_count += 1
            data = response.json()
            fetched_markets = data.get("markets", [])
            if not fetched_markets: # Stop if no markets are returned
                 print("Warning: Received empty market list from Kalshi API.")
                 break
            kalshi_markets.extend(fetched_markets)
            cursor = data.get("cursor")
            if not cursor:
                break
        else:
             print(f"Warning: Reached max API calls ({max_calls}) without finding the end of Kalshi markets.")

        with open(KALSHI_FILE_PATH, "w", encoding="utf-8") as file:
            json.dump({"markets": kalshi_markets}, file, indent=4)
        print(f"Kalshi data fetched successfully. Total API calls made: {call_count}. Saved to {KALSHI_FILE_PATH}")
        return True # Indicate success

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Kalshi data: {e}")
        return False
    except json.JSONDecodeError:
        print("Error decoding Kalshi API response.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during Kalshi data fetch: {e}")
        return False


# --- Email Sending Function ---
def send_email(subject, body):
    if SENDER_PASSWORD == "Secret not available!":
         print("!!! Email configuration missing (SENDER_PASSWORD environment variable not set). Email not sent.")
         print(f"Subject: {subject}")
         print(f"Body: {body}")
         return

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
    except smtplib.SMTPAuthenticationError:
        print("Error sending email: SMTP Authentication Error. Check SENDER_EMAIL and SENDER_PASSWORD (use App Password for Gmail if 2FA is enabled).")
    except Exception as e:
        print(f"Error sending email: {e}")

# --- Temperature and Market Logic ---

def get_chicago_temps_from_api(api_url, target_date_str_for_filtering):
    """
    Fetches temperature data from the Mesowest API and extracts temps for the target date.
    Returns the max temp, latest temp, and if the max temp might have been reached.
    """
    print(f"Fetching temperature data from: {api_url}")
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None, None, False
    except json.JSONDecodeError:
        print("Error: Could not decode JSON response from API")
        return None, None, False
    except Exception as e:
        print(f"An unexpected error occurred during API call or parsing: {e}")
        return None, None, False

    temps_today = []
    if not data or "STATION" not in data or not data["STATION"] or "OBSERVATIONS" not in data["STATION"][0]:
        print("Error: Unexpected API response structure.")
        print(f"API Response Snippet: {str(data)[:500]}")
        return None, None, False

    observations = data.get("STATION", [])[0].get("OBSERVATIONS", {})
    dates = observations.get("date_time", [])
    air_temps = observations.get("air_temp_set_1", [])

    if not dates or not air_temps:
        print("Error: 'date_time' or 'air_temp_set_1' missing in API response observations.")
        return None, None, False

    # Use the dynamically determined date object for filtering
    target_dt_obj = datetime.strptime(target_date_str_for_filtering, "%Y-%m-%d").date()
    latest_temp_today = None
    latest_dt_today = None

    for dt_str, temp in zip(dates, air_temps):
        print(f"Processing date: {dt_str}, temp: {temp}") # Debugging line
        if temp is None: continue
        try:
            # Important: API provides timezone info, so fromisoformat works directly
            current_dt_obj = datetime.fromisoformat(dt_str)
            # Compare just the date part
            current_date_part = current_dt_obj.date()

            if current_date_part == target_dt_obj:
                float_temp = float(temp)
                temps_today.append(float_temp)
                # Update latest temp and time only if this observation is later
                if latest_dt_today is None or current_dt_obj > latest_dt_today:
                    latest_temp_today = float_temp
                    latest_dt_today = current_dt_obj
        except (ValueError, TypeError) as e:
             # print(f"Skipping invalid date/temp entry: {dt_str}, {temp} - Error: {e}")
            continue

    if not temps_today:
        print(f"No temperature data found for {target_date_str_for_filtering} in the fetched API data.")
        return None, None, False

    max_temp_today = max(temps_today)
    high_temp_reached = (latest_temp_today is not None) and (latest_temp_today < max_temp_today)

    print(f"Data for {target_date_str_for_filtering}: Max Temp = {max_temp_today}°F, Latest Temp = {latest_temp_today}°F (at {latest_dt_today})")
    print(f"Has high temp potentially been reached? {'Yes' if high_temp_reached else 'No'}")

    return max_temp_today, latest_temp_today, high_temp_reached

def parse_subtitle_condition(subtitle):
    """ Parses the subtitle string to determine the temperature condition. """
    if not subtitle:
        return None, None

    subtitle = subtitle.replace('\u00b0', '') # Remove degree symbol

    match_between = re.search(r"(\d+(?:\.\d+)?)\s*to\s*(\d+(?:\.\d+)?)\b", subtitle)
    if match_between:
        try:
            low = float(match_between.group(1))
            high = float(match_between.group(2))
            return "between", (low, high)
        except (ValueError, IndexError): pass

    match_above = re.search(r"(\d+(?:\.\d+)?)\s*or\s*above\b", subtitle)
    if match_above:
        try:
            threshold = float(match_above.group(1))
            return "above", threshold
        except (ValueError, IndexError): pass

    match_below = re.search(r"(\d+(?:\.\d+)?)\s*or\s*below\b", subtitle)
    if match_below:
        try:
            threshold = float(match_below.group(1))
            return "below", threshold
        except (ValueError, IndexError): pass

    # print(f"  - Could not parse subtitle: '{subtitle}'") # Reduce noise
    return None, None

def check_temp_condition(int_temp, condition_type, thresholds):
    """ Checks if the integer temperature meets the parsed condition. """
    if condition_type == "between":
        low, high = thresholds
        return low <= int_temp <= high
    elif condition_type == "above":
        threshold = thresholds
        return int_temp >= threshold
    elif condition_type == "below":
        threshold = thresholds
        return int_temp <= threshold
    return False

def check_kalshi_markets(kalshi_file_path, max_temp_today, target_date_ticker_format):
    """
    Loads Kalshi markets, filters for Chicago temp markets for the target date,
    finds ALL contracts matching the max temp based on subtitle, and checks their yes_ask price.
    Returns a list of (ticker, yes_ask) tuples for markets meeting alert criteria.
    """
    if max_temp_today is None or target_date_ticker_format is None:
        print("Error: Cannot check Kalshi markets without valid max temp or target date format.")
        return []

    try:
        with open(kalshi_file_path, 'r') as f:
            data = json.load(f)
            markets = data.get("markets", [])
    except FileNotFoundError:
        print(f"Error: File not found at {kalshi_file_path}. Make sure pull_kalshi_data ran successfully.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {kalshi_file_path}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred loading Kalshi data: {e}")
        return []

    alert_candidates = []
    int_max_temp = math.floor(max_temp_today)

    print(f"\nChecking Kalshi markets for date {target_date_ticker_format} where subtitle condition is met by max temp: {int_max_temp}°F")

    for market in markets:
        ticker = market.get("ticker", "")
        subtitle = market.get("subtitle")
        yes_ask = market.get("yes_ask")

        # 1. Filter by Ticker Prefix
        if not ticker.startswith("KXHIGHCHI"):
            continue

        # 2. Filter by Date in Ticker
        ticker_parts = ticker.split('-')
        if len(ticker_parts) < 3: continue
        ticker_date_str = ticker_parts[1]
        if ticker_date_str != target_date_ticker_format:
            continue

        # Market is for the correct category and date, now check conditions
        print(f"\n  Checking Market: {ticker}")
        if not subtitle:
            print("  - Skipping market: No subtitle found.")
            continue
        # print(f"  Subtitle: '{subtitle}'") # Reduce noise

        # 3. Check Subtitle Condition against Max Temp
        condition_type, thresholds = parse_subtitle_condition(subtitle)

        if condition_type:
            market_matches_temp = check_temp_condition(int_max_temp, condition_type, thresholds)
            # print(f"  - Condition Type: {condition_type}, Threshold(s): {thresholds}") # Reduce noise
            print(f"  - Does Max Temp ({int_max_temp}°F) meet subtitle condition? {'Yes' if market_matches_temp else 'No'}")

            # 4. Check Price if Temp Condition Met
            if market_matches_temp:
                if isinstance(yes_ask, (int, float)) and 0 < yes_ask < 95:
                    print(f"  - Yes Ask ({yes_ask}) is within range (0-95). Adding to alert list.")
                    alert_candidates.append((ticker, yes_ask))
                else:
                    print(f"  - Yes Ask ({yes_ask}) is NOT within range (0-95).")
        # else: # Reduce noise
            # print("  - Failed to determine condition from subtitle.")


    if not alert_candidates:
        print(f"\nNo Kalshi markets found meeting date ({target_date_ticker_format}), temperature ({int_max_temp}°F), and price criteria.")
    else:
        print(f"\nFound {len(alert_candidates)} market(s) meeting alert criteria.")

    return alert_candidates


# --- Main Execution ---
if __name__ == "__main__":
    print(f"--- Starting Check for {TARGET_DATE_TEMP_API_STR} ({TARGET_DATE_TICKER_STR}) ---")
    print(f"Using Sender Email: {SENDER_EMAIL}")
    if SENDER_PASSWORD == "Secret not available!":
        print("WARNING: SENDER_PASSWORD environment variable not set. Email sending will likely fail.")

    # 1. Get Temperature Info from API for the current date
    max_temp, latest_temp, high_reached = get_chicago_temps_from_api(TEMP_API_URL, TARGET_DATE_TEMP_API_STR)

    # 2. Check if high temp potentially reached
    if max_temp is None:
         print("Could not retrieve or process temperature data. Exiting.")
    elif not high_reached:
        print("Highest temperature for the day may not have been reached yet (or latest reading is max). No alert sent.")
    else:
        # 3. Fetch latest Kalshi Data
        if not pull_kalshi_data(): # Fetch latest markets into kalshi_markets.json
            print("Failed to fetch Kalshi market data. Cannot proceed with market check.")
        else:
            # 4. Find ALL corresponding Kalshi markets and check price based on subtitle and date
            alert_list = check_kalshi_markets(KALSHI_FILE_PATH, max_temp, TARGET_DATE_TICKER_STR)

            # 5. Send email if any conditions met
            if alert_list:
                subject = f"Kalshi Alert: Chicago High Temp Market(s) for {TARGET_DATE_TICKER_STR}"
                body_intro = (f"The highest temperature in Chicago for {TARGET_DATE_TEMP_API_STR} appears to have been reached "
                              f"at {math.floor(max_temp)}°F (latest reading was {latest_temp}°F).\n\n"
                              f"The following market(s) for {TARGET_DATE_TICKER_STR} match this temperature and have a yes_ask price between 0 and 95:\n")
                body_markets = ""
                for ticker, yes_ask in alert_list:
                     body_markets += f"- {ticker}: yes_ask = {yes_ask}\n"

                send_email(subject, body_intro + body_markets)
            else:
                # Message already printed in check_kalshi_markets if no candidates found
                pass

    print("\n--- Check complete. ---")