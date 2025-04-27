import json
import smtplib
from email.mime.text import MIMEText
import os
from datetime import datetime, date, timezone # Added timezone
import math
import requests
import re
from decimal import Decimal, ROUND_HALF_UP # Import Decimal for accurate rounding

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
current_date = datetime.now().date()
TARGET_DATE_TEMP_API_STR = current_date.strftime("%Y-%m-%d")
TARGET_DATE_TICKER_STR = current_date.strftime("%d%b%y").upper() # Corrected format DDMMMYY

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
                 # print("Warning: Received empty market list from Kalshi API.") # Reduce noise
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

# --- NWS Rounding Function ---
def nws_round(temp_f):
    """
    Rounds a temperature according to NWS rules described by user.
    - Standard rounding (.5 up) for positive numbers.
    - Special rules for -2.1 to -2.9 F.
    - Standard rounding (.5 away from zero) for other negative numbers.
    """
    # Handle special negative cases first
    # Note: Ensure ranges are mutually exclusive and cover the specified points
    if -2.5 <= temp_f <= -2.1: # Rounds up to -2
        return -2
    if -3.0 < temp_f <= -2.6:  # Rounds down to -3 (Corrected logic for range)
         return -3
    # Add more specific negative ranges here if needed

    # Use Decimal for accurate standard rounding (half up, which rounds away from zero for negatives)
    # Handles positive .5 rounding up, negative .5 rounding down (e.g., -2.5 -> -3)
    try:
        return int(Decimal(str(temp_f)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except Exception as e:
        print(f"Error during NWS rounding for {temp_f}: {e}")
        # Fallback or default behavior if Decimal fails
        return math.floor(temp_f) # Or raise an error, or return None


# --- Temperature and Market Logic ---

def get_chicago_temps_from_api(api_url, target_date_str_for_filtering):
    """
    Fetches temperature data from the Mesowest API and extracts temps for the target date.
    Returns the max temp (float), latest temp (float), and if the max temp might have been reached.
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
        return None, None, False

    observations = data.get("STATION", [])[0].get("OBSERVATIONS", {})
    dates = observations.get("date_time", [])
    air_temps = observations.get("air_temp_set_1", [])

    if not dates or not air_temps:
        print("Error: 'date_time' or 'air_temp_set_1' missing in API response observations.")
        return None, None, False

    target_dt_obj = datetime.strptime(target_date_str_for_filtering, "%Y-%m-%d").date()
    latest_temp_today = None
    latest_dt_today = None

    for dt_str, temp in zip(dates, air_temps):
        if temp is None: continue
        try:
            current_dt_obj = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
            current_date_part = current_dt_obj.date()
            if current_date_part == target_dt_obj:
                float_temp = float(temp)
                temps_today.append(float_temp)
                if latest_dt_today is None or current_dt_obj > latest_dt_today:
                    latest_temp_today = float_temp
                    latest_dt_today = current_dt_obj
        except (ValueError, TypeError) as e:
            print(f"Skipping invalid date/temp entry: {dt_str}, {temp} - Error: {e}")
            continue

    if not temps_today:
        print(f"No temperature data found for {target_date_str_for_filtering} in the fetched API data.")
        return None, None, False

    max_temp_today = max(temps_today)
    high_temp_reached = (latest_temp_today is not None) and (latest_temp_today < max_temp_today)

    # Apply NWS rounding here for reporting/checking
    nws_rounded_max_temp = nws_round(max_temp_today)

    print(f"Data for {target_date_str_for_filtering}: Max Temp = {max_temp_today:.2f}°F (NWS Rounded: {nws_rounded_max_temp}°F), Latest Temp = {latest_temp_today}°F (at {latest_dt_today})")
    print(f"Has high temp potentially been reached? {'Yes' if high_temp_reached else 'No'}")

    # Return the original float max_temp, rounding will happen in check_kalshi_markets
    return max_temp_today, latest_temp_today, high_temp_reached

def parse_subtitle_condition(subtitle):
    """ Parses the subtitle string to determine the temperature condition. """
    if not subtitle: return None, None
    subtitle = subtitle.replace('\u00b0', '') # Remove degree symbol

    match_between = re.search(r"(\d+(?:\.\d+)?)\s*to\s*(\d+(?:\.\d+)?)\b", subtitle)
    if match_between:
        try: return "between", (float(match_between.group(1)), float(match_between.group(2)))
        except (ValueError, IndexError): pass

    match_above = re.search(r"(\d+(?:\.\d+)?)\s*or\s*above\b", subtitle)
    if match_above:
        try: return "above", float(match_above.group(1))
        except (ValueError, IndexError): pass

    match_below = re.search(r"(\d+(?:\.\d+)?)\s*or\s*below\b", subtitle)
    if match_below:
        try: return "below", float(match_below.group(1))
        except (ValueError, IndexError): pass

    return None, None

def check_temp_resolves_yes(rounded_temp, condition_type, thresholds):
    """ Checks if the NWS rounded integer temperature meets the condition for a 'Yes' resolution. """
    if condition_type == "between":
        low, high = thresholds
        # For ranges like "77 to 78", check if rounded temp is 77 or 78
        return math.floor(low) <= rounded_temp <= math.floor(high)
    elif condition_type == "above":
        threshold = thresholds
         # For "76 or above", check if rounded temp is >= 77 (or >= threshold + 1 for integer threshold)
         # If threshold has decimal part, compare directly
        if threshold == math.floor(threshold): # Integer threshold like 76
             return rounded_temp >= (threshold + 1)
        else: # Non-integer threshold, e.g. 76.5 - less common in subtitles?
             return rounded_temp >= math.ceil(threshold) # Need clarification on how Kalshi handles non-int thresholds
    elif condition_type == "below":
        threshold = thresholds
        # For "76 or below", check if rounded temp <= 76
        return rounded_temp <= math.floor(threshold)
    return False

def check_temp_resolves_no(rounded_temp, condition_type, thresholds):
    """ Checks if the NWS rounded integer temperature meets the condition for a 'No' resolution. """
    if condition_type == "between":
        low, high = thresholds
        # Resolves No if rounded temp is below the range floor OR above the range ceiling
        return rounded_temp < math.floor(low) or rounded_temp > math.floor(high)
    elif condition_type == "above":
        threshold = thresholds
        # If "76 or above" is YES (>=77), then <= 76 is NO
        if threshold == math.floor(threshold):
            return rounded_temp <= threshold
        else:
            # This case needs clarification on Kalshi rules for non-int thresholds
            return rounded_temp < math.ceil(threshold)
    elif condition_type == "below":
        threshold = thresholds
        # If "76 or below" is YES (<=76), then >= 77 is NO
        return rounded_temp > math.floor(threshold)
    return False


def check_kalshi_markets(kalshi_file_path, max_temp_today, target_date_ticker_format):
    """
    Loads Kalshi markets, filters for the target date, checks if NWS rounded max temp resolves
    the market to YES or NO based on subtitle, checks the corresponding ask price (yes_ask or no_ask).
    Returns a list of (ticker, price, resolution) tuples for markets meeting alert criteria.
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
    # Apply NWS rounding to the max temp for checking conditions
    nws_rounded_temp = nws_round(max_temp_today)
    print(f"\nChecking Kalshi markets for date {target_date_ticker_format} based on NWS Rounded max temp: {nws_rounded_temp}°F (Original: {max_temp_today:.2f}°F)")

    for market in markets:
        ticker = market.get("ticker", "")
        subtitle = market.get("subtitle")
        yes_ask = market.get("yes_ask")
        no_ask = market.get("no_ask")

        if not ticker.startswith("KXHIGHCHI"): continue
        ticker_parts = ticker.split('-')
        if len(ticker_parts) < 3: continue
        ticker_date_str = ticker_parts[1]
        if ticker_date_str != target_date_ticker_format: continue

        print(f"\n  Checking Market: {ticker}")
        if not subtitle:
            print("  - Skipping market: No subtitle found.")
            continue

        condition_type, thresholds = parse_subtitle_condition(subtitle)
        if not condition_type:
            print(f"  - Could not parse subtitle: '{subtitle}'")
            continue

        print(f"  - Subtitle Condition: {condition_type}, Threshold(s): {thresholds}")

        # Use nws_rounded_temp for checking resolutions
        resolves_yes = check_temp_resolves_yes(nws_rounded_temp, condition_type, thresholds)
        if resolves_yes:
            print(f"  - NWS Rounded Temp ({nws_rounded_temp}°F) meets 'Yes' condition.")
            if isinstance(yes_ask, (int, float)) and 0 < yes_ask < 95:
                print(f"  - Yes Ask ({yes_ask}) is within range (0-95). Adding 'Yes' alert.")
                alert_candidates.append((ticker, yes_ask, "Yes"))
            else:
                print(f"  - Yes Ask ({yes_ask}) is NOT within range (0-95).")
        else:
            resolves_no = check_temp_resolves_no(nws_rounded_temp, condition_type, thresholds)
            if resolves_no:
                 print(f"  - NWS Rounded Temp ({nws_rounded_temp}°F) meets 'No' condition.")
                 if isinstance(no_ask, (int, float)) and 0 < no_ask < 95:
                     print(f"  - No Ask ({no_ask}) is within range (0-95). Adding 'No' alert.")
                     alert_candidates.append((ticker, no_ask, "No"))
                 else:
                     print(f"  - No Ask ({no_ask}) is NOT within range (0-95).")
            else:
                 print(f"  - NWS Rounded Temp ({nws_rounded_temp}°F) does not definitively meet 'Yes' or 'No' condition based on subtitle.")

    if not alert_candidates:
        print(f"\nNo Kalshi markets found meeting date ({target_date_ticker_format}), resolution (Yes/No for {nws_rounded_temp}°F), and price criteria.")
    else:
        print(f"\nFound {len(alert_candidates)} market alert(s) based on current NWS rounded max temp.")

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
        print("Highest temperature for the day may not have been reached yet (or latest reading is max). No alert needed based on resolved contracts.")
    else:
        # High temp is reached, now check if this resolves any contracts
        nws_rounded_max_temp = nws_round(max_temp) # Round the max temp here for reporting
        print(f"Highest temp ({nws_rounded_max_temp}°F NWS Rounded) appears reached. Checking resolved contracts...")
        # 3. Fetch latest Kalshi Data
        if not pull_kalshi_data(): # Fetch latest markets into kalshi_markets.json
            print("Failed to fetch Kalshi market data. Cannot proceed with market check.")
        else:
            # 4. Find ALL corresponding Kalshi markets and check price based on subtitle, date, and resolution
            # Pass the original float max_temp; rounding happens inside check_kalshi_markets
            alert_list = check_kalshi_markets(KALSHI_FILE_PATH, max_temp, TARGET_DATE_TICKER_STR)

            # 5. Send email if any conditions met
            if alert_list:
                subject = f"Kalshi Alert: Chicago High Temp Market(s) Resolved for {TARGET_DATE_TICKER_STR}"
                body_intro = (f"The highest temperature in Chicago for {TARGET_DATE_TEMP_API_STR} appears to have been reached "
                              f"at {max_temp:.2f}°F (NWS Rounded: {nws_rounded_max_temp}°F). Latest reading was {latest_temp}°F.\n\n" # Include original and rounded
                              f"This NWS rounded max temp resolves the following market(s) with ask prices between 0 and 95:\n")
                body_markets = ""
                for ticker, price, resolution in alert_list:
                     price_type = "yes_ask" if resolution == "Yes" else "no_ask"
                     body_markets += f"- {ticker}: Resolved to '{resolution}', {price_type} = {price}\n"

                send_email(subject, body_intro + body_markets)
            else:
                # Message already printed in check_kalshi_markets if no candidates found
                pass

    print("\n--- Check complete. ---")