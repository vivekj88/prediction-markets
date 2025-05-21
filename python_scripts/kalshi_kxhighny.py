import json
import smtplib
from email.mime.text import MIMEText
import os
from datetime import datetime, date, timezone, timedelta
import math
import requests
import re
from kalshi_utils import nws_round
from kalshi_utils import celsius_to_fahrenheit
from decimal import Decimal

# --- Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "vivek.zapier@gmail.com")

try:
    SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
except KeyError:
    SENDER_PASSWORD = "Secret not available!"
    print("Warning: SENDER_PASSWORD environment variable not set.")

RECIPIENT_EMAIL = "vivek.zapier@gmail.com"
KALSHI_FILE_PATH = "kalshi_markets.json"

# --- Timezone Configuration ---
TARGET_TIMEZONE_ABBR = "EST" # <<< SET YOUR DESIRED STANDARD TIMEZONE HERE
STANDARD_OFFSETS = {
    "EST": -5, "CST": -6, "MST": -7, "PST": -8,
}

if TARGET_TIMEZONE_ABBR not in STANDARD_OFFSETS:
    print(f"Error: Unknown TARGET_TIMEZONE_ABBR '{TARGET_TIMEZONE_ABBR}'. Please use a defined standard abbreviation.")
    exit()

TARGET_STANDARD_OFFSET_HOURS = STANDARD_OFFSETS[TARGET_TIMEZONE_ABBR]
target_standard_offset_tz = timezone(timedelta(hours=TARGET_STANDARD_OFFSET_HOURS))

# --- Dynamically determine target date based on UTC -> Target Standard Time ---
now_utc = datetime.now(timezone.utc)
now_target_standard_tz = now_utc.astimezone(target_standard_offset_tz)
target_date_obj = now_target_standard_tz.date()

TARGET_DATE_TEMP_API_STR = target_date_obj.strftime("%Y-%m-%d")
TARGET_DATE_TICKER_STR = target_date_obj.strftime("%y%b%d").upper() # User specified format
print(f"Determined Target Date (based on UTC -> Fixed {TARGET_TIMEZONE_ABBR} offset UTC{TARGET_STANDARD_OFFSET_HOURS:+d}): {TARGET_DATE_TEMP_API_STR}")
print(f"Targeting Kalshi tickers containing date: {TARGET_DATE_TICKER_STR} (Format: YYMONDD)")

# API Endpoint Configuration
STATION_ID = "KNYC"
STATION_USUAL_TIME = "1-3 PM CT"
MESOWEST_TOKEN = "d8c6aee36a994f90857925cea26934be"
TEMP_API_URL = f"https://api.mesowest.net/v2/stations/timeseries?STID={STATION_ID}&showemptystations=1&units=temp%7CC,speed%7Cmph,english&recent=4320&token={MESOWEST_TOKEN}&complete=1&obtimezone=local"

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
    max_calls = 1500
    try:
        for _ in range(max_calls):
            if cursor: params["cursor"] = cursor
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            call_count += 1
            data = response.json()
            fetched_markets = data.get("markets", [])
            if not fetched_markets: break
            kalshi_markets.extend(fetched_markets)
            cursor = data.get("cursor")
            if not cursor: break
        else:
            print(f"Warning: Reached max API calls ({max_calls}).")

        with open(KALSHI_FILE_PATH, "w", encoding="utf-8") as file:
            json.dump({"markets": kalshi_markets}, file, indent=4)
        print(f"Kalshi data fetched successfully. Total API calls made: {call_count}. Saved to {KALSHI_FILE_PATH}")
        return True
    except requests.exceptions.RequestException as e: print(f"Error fetching Kalshi data: {e}"); return False
    except json.JSONDecodeError: print("Error decoding Kalshi API response."); return False
    except Exception as e: print(f"An unexpected error occurred during Kalshi data fetch: {e}"); return False

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
    except smtplib.SMTPAuthenticationError: print("Error sending email: SMTP Authentication Error."); return
    except Exception as e: print(f"Error sending email: {e}"); return

# --- Temperature and Market Logic ---
def get_station_temps_from_api(api_url, target_date_str_to_filter):
    """
    Fetches temperature data from the Mesowest API for the target date.
    Handles 5-min cadence for max temp (rounded Celsius) by using lowest unrounded value,
    and non-5-min cadence (unrounded Celsius). Converts temperatures to Fahrenheit for output,
    applies NWS rounding to max_temp_today.
    Returns: max_temp_today (°F, float), latest_temp_today (°F, float), high_reached (bool),
             temp_data_list (list of (datetime, float °F)), station_reported_tz (str)
    """
    print(f"Fetching temperature data from: {api_url}")
    target_dt_obj = datetime.strptime(target_date_str_to_filter, "%Y-%m-%d").date()
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None, None, False, [], None
    except json.JSONDecodeError:
        print("Error: Could not decode JSON response from API")
        return None, None, False, [], None
    except Exception as e:
        print(f"An unexpected error occurred during API call or parsing: {e}")
        return None, None, False, [], None

    if not data or "STATION" not in data or not data["STATION"] or "OBSERVATIONS" not in data["STATION"][0]:
        print("Error: Unexpected API response structure.")
        return None, None, False, [], None

    observations = data["STATION"][0].get("OBSERVATIONS", {})
    dates = observations.get("date_time", [])
    air_temps = observations.get("air_temp_set_1", [])
    station_reported_tz = data["STATION"][0].get("TIMEZONE")

    if not dates or not air_temps:
        print("Error: 'date_time' or 'air_temp_set_1' missing.")
        return None, None, False, [], station_reported_tz

    temp_data_list = []
    celsius_temps = []
    latest_temp_celsius = None
    latest_dt_today = None
    max_temp_celsius = None
    max_temp_dt = None

    for dt_str, temp in zip(dates, air_temps):
        if temp is None:
            continue
        try:
            current_dt_obj = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
            current_date_part = current_dt_obj.date()
            if current_date_part == target_dt_obj:
                float_temp_celsius = float(temp)
                celsius_temps.append(float_temp_celsius)
                temp_data_list.append((current_dt_obj, celsius_to_fahrenheit(float_temp_celsius)))
                # Track latest temperature
                if latest_dt_today is None or current_dt_obj > latest_dt_today:
                    latest_temp_celsius = float_temp_celsius
                    latest_dt_today = current_dt_obj
                # Track max temperature and its timestamp
                if max_temp_celsius is None or float_temp_celsius > max_temp_celsius:
                    max_temp_celsius = float_temp_celsius
                    max_temp_dt = current_dt_obj
        except (ValueError, TypeError):
            continue

    if not temp_data_list:
        print(f"No temperature data found for target date {target_date_str_to_filter} in API data (Station TZ: {station_reported_tz}).")
        return None, None, False, [], station_reported_tz

    temp_data_list.sort(key=lambda x: x[0])

    # Check if max_temp_celsius's timestamp is on 5-minute cadence
    is_max_on_5min_cadence = max_temp_dt.minute % 5 == 0 if max_temp_dt else False

    # Adjust max_temp_celsius for lowest unrounded value if on 5-min cadence
    if is_max_on_5min_cadence:
        max_temp_decimal = Decimal(str(max_temp_celsius))
        integer_part = int(max_temp_decimal)
        fractional_part = abs(max_temp_decimal - integer_part)
        if fractional_part == Decimal('0.0'):
            max_temp_celsius = float(max_temp_decimal - Decimal('0.5'))  # e.g., 32°C → 31.5°C
        elif fractional_part == Decimal('0.5') and max_temp_celsius < 0:
            max_temp_celsius = float(max_temp_decimal - Decimal('0.5'))  # e.g., -3.5°C → -4.0°C
        elif fractional_part == Decimal('0.5') and max_temp_celsius >= 0:
            max_temp_celsius = float(max_temp_decimal)  # e.g., 3.5°C → 3.5°C (already lowest)

    # Convert max_temp and latest_temp to Fahrenheit
    max_temp_today = celsius_to_fahrenheit(max_temp_celsius)
    latest_temp_today = celsius_to_fahrenheit(latest_temp_celsius) if latest_temp_celsius is not None else None

    # Round max_temp_today using NWS rules
    nws_rounded_max_temp = nws_round(max_temp_today)

    high_temp_reached = (latest_temp_today is not None) and (latest_temp_today < max_temp_today)

    print(f"Data for target date {target_date_str_to_filter}: Max Temp = {max_temp_today:.2f}°F (NWS Rounded: {nws_rounded_max_temp}°F), Latest Temp = {latest_temp_today:.2f}°F (at {latest_dt_today})")
    print(f"Has high temp potentially been reached? {'Yes' if high_temp_reached else 'No'}")

    print(f"max_temp_dt: {max_temp_dt})")
    return max_temp_today, latest_temp_today, high_temp_reached, temp_data_list, station_reported_tz

def parse_subtitle_condition(subtitle):
    """ Parses the subtitle string to determine the temperature condition. """
    if not subtitle: return None, None
    subtitle = subtitle.replace('\u00b0', '')

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

def check_kalshi_markets(kalshi_file_path, max_temp_today, target_date_ticker_format):
    """
    Loads Kalshi markets for the target date, checks if markets entirely below the lower bound
    of the NWS rounded max temp ±2°F resolve to 'No', and verifies no_ask prices are between 0 and 95.
    Returns a list of (ticker, no_ask, 'No') tuples for qualifying markets.
    """
    if max_temp_today is None or target_date_ticker_format is None:
        print("Error: Cannot check Kalshi markets without valid max temp or target date format.")
        return []

    try:
        with open(kalshi_file_path, 'r') as f:
            data = json.load(f)
            markets = data.get("markets", [])
    except FileNotFoundError: print(f"Error: File not found at {kalshi_file_path}."); return []
    except json.JSONDecodeError: print(f"Error: Could not decode JSON from {kalshi_file_path}"); return []
    except Exception as e: print(f"An unexpected error occurred loading Kalshi data: {e}"); return []

    alert_candidates = []
    nws_rounded_temp = nws_round(max_temp_today)
    error_threshold = 0  # ±2°F
    temp_range_lower = nws_rounded_temp - error_threshold
    temp_range_upper = nws_rounded_temp + error_threshold
    print(f"\nChecking Kalshi markets for date {target_date_ticker_format} for 'No' resolution (markets entirely below {temp_range_lower}°F)")

    for market in markets:
        ticker = market.get("ticker", "")
        subtitle = market.get("yes_sub_title")
        no_ask = market.get("no_ask")

        if not ticker.startswith("KXHIGHNY"): continue
        ticker_parts = ticker.split('-')
        if len(ticker_parts) < 3: continue
        ticker_date_str = ticker_parts[1]
        if ticker_date_str != target_date_ticker_format: continue

        print(f"\n  Checking Market: {ticker}")
        if not subtitle: print("  - Skipping market: No yes_sub_title found."); continue

        condition_type, thresholds = parse_subtitle_condition(subtitle)
        if not condition_type: print(f"  - Could not parse yes_sub_title: '{subtitle}'"); continue

        print(f"  - yes_sub_title Condition: {condition_type}, Threshold(s): {thresholds}")

        # Check if the market condition is entirely below the temp range lower bound
        is_below_range = False
        if condition_type == "between":
            low, high = thresholds
            if high < temp_range_lower:
                is_below_range = True
        elif condition_type == "below":
            threshold = thresholds
            if threshold < temp_range_lower:
                is_below_range = True
        elif condition_type == "above":
            # "Above" markets cannot be entirely below the range
            is_below_range = False

        if is_below_range:
            print(f"  - Market condition ({condition_type} {thresholds}) is entirely below temp range lower bound ({temp_range_lower}°F).")
            # Check if the market resolves to 'No' based on NWS rounded temp
            resolves_no = False
            if condition_type == "between":
                low, high = thresholds
                resolves_no = nws_rounded_temp < math.floor(low) or nws_rounded_temp > math.floor(high)
            elif condition_type == "below":
                threshold = thresholds
                resolves_no = nws_rounded_temp > math.floor(threshold)

            if resolves_no:
                print(f"  - NWS Rounded Temp ({nws_rounded_temp}°F) resolves market to 'No'.")
                if isinstance(no_ask, (int, float)) and 0 < no_ask < 95:
                    print(f"  - No Ask ({no_ask}) is within range (0-95). Adding 'No' alert.")
                    alert_candidates.append((ticker, no_ask, "No"))
                else:
                    print(f"  - No Ask ({no_ask}) is NOT within range (0-95).")
            else:
                print(f"  - NWS Rounded Temp ({nws_rounded_temp}°F) does NOT resolve market to 'No'.")
        else:
            print(f"  - Market condition ({condition_type} {thresholds}) is NOT entirely below temp range lower bound ({temp_range_lower}°F).")

    if not alert_candidates:
        print(f"\nNo Kalshi markets found resolving to 'No' (entirely below {temp_range_lower}°F) with valid no_ask for date {target_date_ticker_format}.")
    else:
        print(f"\nFound {len(alert_candidates)} market alert(s) based on 'No' resolution and price.")

    return alert_candidates

# --- Main Execution ---
if __name__ == "__main__":
    print(f"--- Starting Check for Date: {TARGET_DATE_TEMP_API_STR} (Ticker Format: {TARGET_DATE_TICKER_STR}) ---")
    print(f"Using Sender Email: {SENDER_EMAIL}")
    if SENDER_PASSWORD == "Secret not available!":
        print("WARNING: SENDER_PASSWORD environment variable not set. Email sending will likely fail.")

    # 1. Get Temperature Info from API for the calculated target date
    max_temp, latest_temp, high_temp_reached, temp_data_list, station_reported_tz = get_station_temps_from_api(TEMP_API_URL, TARGET_DATE_TEMP_API_STR)

    # 2. Check if high temp potentially reached
    if max_temp is None:
        print("Could not retrieve or process temperature data. Exiting.")
    # elif not high_temp_reached:
    #     print("Highest temperature for the day may not have been reached yet (or latest reading is max). No alert needed based on resolved contracts.")
    else:
        # High temp is reached, now check if this resolves any contracts to NO
        nws_rounded_max_temp = nws_round(max_temp)
        print(f"Highest temp ({nws_rounded_max_temp}°F NWS Rounded) appears reached. Checking contracts resolving to 'No'...")

        if not pull_kalshi_data(): # Fetch latest markets
            print("Failed to fetch Kalshi market data. Cannot proceed with market check.")
        else:
            # Find Kalshi markets resolving to NO and check price
            alert_list = check_kalshi_markets(KALSHI_FILE_PATH, max_temp, TARGET_DATE_TICKER_STR)

            if alert_list:
                subject = f"Kalshi Alert: High Temp {STATION_ID} {STATION_USUAL_TIME} Market(s) Resolved NO for {TARGET_DATE_TICKER_STR}"
                body_intro = (f"The highest temperature reported for {STATION_ID} on {TARGET_DATE_TEMP_API_STR} appears36 to have been reached "
                              f"at {max_temp:.2f}°F (NWS Rounded: {nws_rounded_max_temp}°F). Latest reading was {latest_temp}°F.\n\n"
                              f"This NWS rounded max temp resolves the following market(s) entirely below "
                              f"{nws_rounded_max_temp - 2}°F to 'No' with no_ask prices between 0 and 95, indicating potential opportunities to buy 'No' contracts:\n")
                body_markets = ""
                for ticker, price, resolution in alert_list:
                    body_markets += f"- {ticker}: Resolved to '{resolution}', no_ask = {price}\n"

                # Prepare temperature log for email body
                body_temp_log = f"\n\nTemperature Log for {TARGET_DATE_TEMP_API_STR} (Timezone: {station_reported_tz or 'N/A'}):\n"
                body_temp_log += "------------------------------------\n"
                if temp_data_list:
                    for dt_obj, temp_val in temp_data_list:
                        time_str = dt_obj.strftime("%H:%M:%S %z")
                        highlight = " *** MAX ***" if temp_val == max_temp else ""
                        body_temp_log += f"{time_str}: {temp_val:.2f}°F{highlight}\n"
                else:
                    body_temp_log += "No temperature data available for this date.\n"
                body_temp_log += "------------------------------------\n"

                # Combine parts and send email
                send_email(subject, body_intro + body_markets + body_temp_log)

    print("\n--- Check complete. ---")