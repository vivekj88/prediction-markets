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
from kalshi_utils import get_station_temps_from_api

# --- Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "vivek.zapier@gmail.com")

# --- NEW PROBABILISTIC APPROACH CONFIGURATION ---
USE_PROBABILISTIC_APPROACH = False  # Set to False to use original conservative approach
MIN_EXPECTED_VALUE = 1.0  # Minimum expected value required to trade (in dollars)
PAYOUT_AMOUNT = 100.0  # Standard payout for No contracts

try:
    SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
except KeyError:
    SENDER_PASSWORD = "Secret not available!"
    print("Warning: SENDER_PASSWORD environment variable not set.")

RECIPIENT_EMAIL = "vivek.zapier@gmail.com"
KALSHI_FILE_PATH = "kalshi_markets.json"

# --- Timezone Configuration ---
TARGET_TIMEZONE_ABBR = "PST" # <<< SET YOUR DESIRED STANDARD TIMEZONE HERE
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
TICKER = "KXHIGHLAX"
STATION_ID = "KLAX"
STATION_USUAL_TIME = "4-6 PM CT"
MESOWEST_TOKEN = "d8c6aee36a994f90857925cea26934be"
TEMP_API_URL = f"https://api.mesowest.net/v2/stations/timeseries?STID={STATION_ID}&showemptystations=1&units=temp%7CC,speed%7Cmph,english&recent=4320&token={MESOWEST_TOKEN}&complete=1&obtimezone=local"

# --- Temperature Probability Calculation Functions ---
def celsius_to_fahrenheit_range(celsius_temp):
    """Convert rounded Celsius to Fahrenheit range (min, max)"""
    min_celsius = celsius_temp - 0.5
    max_celsius = celsius_temp + 0.4
    min_fahrenheit = (min_celsius * 9/5) + 32
    max_fahrenheit = (max_celsius * 9/5) + 32

    min_fahrenheit = nws_round(min_fahrenheit)
    max_fahrenheit = nws_round(max_fahrenheit)
    return min_fahrenheit, max_fahrenheit

def fahrenheit_to_celsius(fahrenheit_temp):
    """Convert Fahrenheit to Celsius"""
    return (fahrenheit_temp - 32) * 5/9

def calculate_market_yes_probability(temp_range_f, market_min, market_max):
    """
    Calculate probability that temperature falls within market range (discrete values)
    
    Args:
        temp_range_f: (min_temp, max_temp) in Fahrenheit (inclusive range)
        market_min: Market lower bound in Fahrenheit
        market_max: Market upper bound in Fahrenheit
    
    Returns:
        Probability (0-1) that market resolves to Yes
    """
    temp_min, temp_max = temp_range_f
    
    # Generate all possible discrete temperature values (whole numbers)
    possible_temps = list(range(int(temp_min), int(temp_max) + 1))
    total_possible = len(possible_temps)
    
    if total_possible == 0:
        return 0.0
    
    if market_min > temp_max:
        return 1.0
    
    # Count how many temperatures fall within the market range
    favorable_temps = []
    for temp in possible_temps:
        if market_min <= temp <= market_max:
            favorable_temps.append(temp)
    
    favorable_count = len(favorable_temps)
    
    return favorable_count / total_possible

def calculate_expected_value(no_probability, contract_cost, payout=PAYOUT_AMOUNT):
    """Calculate expected value of a No contract"""
    if no_probability <= 0.5:
        return -1
    return (no_probability * payout) - contract_cost

def analyze_market_probabilistically(max_temp_f, condition_type, thresholds, no_ask, max_temp_on_5min_cadence):
    """
    Analyze a market using probabilistic approach
    
    Returns:
        dict with analysis results
    """
    # Convert Fahrenheit max temp to Celsius reading
    celsius_reading = fahrenheit_to_celsius(max_temp_f)
    
    # Get the possible Fahrenheit range for this Celsius reading
    if max_temp_on_5min_cadence:
        temp_range_f = celsius_to_fahrenheit_range(celsius_reading)
    else:
        temp_range_f = nws_round(max_temp_f), nws_round(max_temp_f)
    
    # Calculate Yes probability based on market condition
    if condition_type == "between":
        market_min, market_max = thresholds
        yes_probability = calculate_market_yes_probability(temp_range_f, market_min, market_max)
    elif condition_type == "below":
        threshold = thresholds
        market_min = -1000  # Arbitrary low 
        market_max = threshold
        # "Below X" means market resolves Yes if temp <= X
        yes_probability = calculate_market_yes_probability(temp_range_f, -1000, threshold)
    elif condition_type == "above":
        threshold = thresholds
        market_min = threshold
        market_max = 1000  # Arbitrary high 
        # "Above X" means market resolves Yes if temp >= X
        yes_probability = calculate_market_yes_probability(temp_range_f, threshold, 1000)
    else:
        yes_probability = 0.0
    
    no_probability = 1.0 - yes_probability
    expected_value = calculate_expected_value(no_probability, no_ask)
    market_implied_no_prob = no_ask / PAYOUT_AMOUNT
    edge = no_probability - market_implied_no_prob
    
    return {
        'celsius_reading': celsius_reading,
        'temp_range_f': temp_range_f,
        'yes_probability': yes_probability,
        'no_probability': no_probability,
        'expected_value': expected_value,
        'market_implied_no_prob': market_implied_no_prob,
        'edge': edge,
        'should_trade': expected_value > MIN_EXPECTED_VALUE
    }

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

def check_kalshi_markets(kalshi_file_path, max_temp_today, target_date_ticker_format, max_temp_on_5min_cadence):
    """
    Loads Kalshi markets for the target date and analyzes them using either
    the original conservative approach or the new probabilistic approach.
    """
    if max_temp_today is None or target_date_ticker_format is None:
        print("Error: Cannot check Kalshi markets without valid max temp or target date format.")
        return [], []

    try:
        with open(kalshi_file_path, 'r') as f:
            data = json.load(f)
            markets = data.get("markets", [])
    except FileNotFoundError: print(f"Error: File not found at {kalshi_file_path}."); return [], []
    except json.JSONDecodeError: print(f"Error: Could not decode JSON from {kalshi_file_path}"); return [], []
    except Exception as e: print(f"An unexpected error occurred loading Kalshi data: {e}"); return [], []

    alert_candidates = []
    all_market_analyses = []
    
    approach_name = "Probabilistic" if USE_PROBABILISTIC_APPROACH else "Conservative"
    print(f"\n=== Using {approach_name} Approach ===")
    
    if USE_PROBABILISTIC_APPROACH:
        print(f"Minimum Expected Value Required: ${MIN_EXPECTED_VALUE}")
    else:
        # Original conservative approach
        nws_rounded_temp = nws_round(max_temp_today)
        error_threshold = 0  # ±2°F
        temp_range_lower = nws_rounded_temp - error_threshold
        print(f"Checking markets entirely below {temp_range_lower}°F (Conservative approach)")

    print(f"\nAnalyzing Kalshi markets for date {target_date_ticker_format}")

    for market in markets:
        ticker = market.get("ticker", "")
        subtitle = market.get("yes_sub_title")
        no_ask = market.get("no_ask")

        if not ticker.startswith(TICKER): continue
        ticker_parts = ticker.split('-')
        if len(ticker_parts) < 3: continue
        ticker_date_str = ticker_parts[1]
        if ticker_date_str != target_date_ticker_format: continue

        print(f"\n  Analyzing Market: {ticker}")
        if not subtitle: print("  - Skipping market: No yes_sub_title found."); continue
        if not isinstance(no_ask, (int, float)): print("  - Skipping market: Invalid no_ask price."); continue

        condition_type, thresholds = parse_subtitle_condition(subtitle)
        if not condition_type: print(f"  - Could not parse yes_sub_title: '{subtitle}'"); continue

        print(f"  - Condition: {condition_type}, Threshold(s): {thresholds}")
        print(f"  - No Ask Price: ${no_ask}")

        if USE_PROBABILISTIC_APPROACH:
            # New probabilistic approach
            analysis = analyze_market_probabilistically(max_temp_today, condition_type, thresholds, no_ask, max_temp_on_5min_cadence)
            
            print(f"  - Celsius Reading: {analysis['celsius_reading']:.2f}°C")
            print(f"  - Temp Range: {analysis['temp_range_f'][0]:.1f}°F - {analysis['temp_range_f'][1]:.1f}°F")
            print(f"  - Yes Probability: {analysis['yes_probability']:.1%}")
            print(f"  - No Probability: {analysis['no_probability']:.1%}")
            print(f"  - Expected Value: ${analysis['expected_value']:.2f}")
            print(f"  - Market Implied No Prob: {analysis['market_implied_no_prob']:.1%}")
            print(f"  - Edge: {analysis['edge']:.1%}")
            
            # Add to all analyses for summary
            market_analysis = {
                'ticker': ticker,
                'condition': f"{condition_type} {thresholds}",
                'no_ask': no_ask,
                **analysis
            }
            all_market_analyses.append(market_analysis)
            
            if analysis['should_trade']:
                print(f"  - TRADE RECOMMENDATION: BUY No (EV: ${analysis['expected_value']:.2f})")
                alert_candidates.append((ticker, no_ask, "No", analysis['no_probability'], analysis['expected_value']))
            else:
                print(f"  - NO TRADE: Expected value too low (${analysis['expected_value']:.2f} < ${MIN_EXPECTED_VALUE})")
                
        else:
            # Original conservative approach
            nws_rounded_temp = nws_round(max_temp_today)
            temp_range_lower = nws_rounded_temp - 0  # error_threshold = 0
            
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
                is_below_range = False

            if is_below_range:
                print(f"  - Market condition is entirely below temp range lower bound ({temp_range_lower}°F).")
                # Check if the market resolves to 'No' based on NWS rounded temp
                resolves_no = False
                if condition_type == "between":
                    low, high = thresholds
                    resolves_no = nws_rounded_temp < math.floor(low) or nws_rounded_temp > math.floor(high)
                elif condition_type == "below":
                    threshold = thresholds
                    resolves_no = nws_rounded_temp > math.floor(threshold)

                if resolves_no and 0 < no_ask < 95:
                    print(f"  - TRADE RECOMMENDATION: BUY No (Conservative approach)")
                    alert_candidates.append((ticker, no_ask, "No", 1.0, 100 - no_ask))  # 100% prob, EV = payout - cost
                else:
                    print(f"  - NO TRADE: Either doesn't resolve to No or price not in range")
            else:
                print(f"  - Market condition is NOT entirely below temp range lower bound.")

    return alert_candidates, all_market_analyses

# --- Main Execution ---
if __name__ == "__main__":
    print(f"--- Starting Check for Date: {TARGET_DATE_TEMP_API_STR} (Ticker Format: {TARGET_DATE_TICKER_STR}) ---")
    print(f"Using Sender Email: {SENDER_EMAIL}")
    print(f"Trading Approach: {'Probabilistic' if USE_PROBABILISTIC_APPROACH else 'Conservative'}")
    
    if SENDER_PASSWORD == "Secret not available!":
        print("WARNING: SENDER_PASSWORD environment variable not set. Email sending will likely fail.")

    # 1. Get Temperature Info from API for the calculated target date
    max_temp, latest_temp, high_temp_reached, temp_data_list, station_reported_tz, max_temp_on_5min_cadence = get_station_temps_from_api(TEMP_API_URL, TARGET_DATE_TEMP_API_STR)

    # 2. Check if we have valid temperature data
    if max_temp is None:
        print("Could not retrieve or process temperature data. Exiting.")
    else:
        nws_rounded_max_temp = nws_round(max_temp)
        print(f"Max temp: {max_temp:.2f}°F (NWS Rounded: {nws_rounded_max_temp}°F)")
        print(f"Latest temp: {latest_temp}°F")

        if not pull_kalshi_data(): # Fetch latest markets
            print("Failed to fetch Kalshi market data. Cannot proceed with market check.")
        else:
            # Find Kalshi markets and analyze them
            alert_list, all_analyses = check_kalshi_markets(KALSHI_FILE_PATH, max_temp, TARGET_DATE_TICKER_STR, max_temp_on_5min_cadence)

            # Prepare email content
            approach_name = "Probabilistic" if USE_PROBABILISTIC_APPROACH else "Conservative"
            
            if alert_list or all_analyses:
                subject = f"Kalshi Alert: {approach_name} Analysis for {TARGET_DATE_TICKER_STR} - {len(alert_list)} Trade Opportunity(ies)"
                
                body_intro = (f"Temperature Analysis for {STATION_ID} on {TARGET_DATE_TEMP_API_STR}:\n"
                             f"Max Temp: {max_temp:.2f}°F (NWS Rounded: {nws_rounded_max_temp}°F)\n"
                             f"Latest Temp: {latest_temp}°F\n"
                             f"Approach: {approach_name}\n\n")

                if alert_list:
                    body_trades = f"=== TRADE RECOMMENDATIONS ({len(alert_list)}) ===\n"
                    for ticker, price, resolution, no_prob, exp_val in alert_list:
                        body_trades += f"• {ticker}: BUY {resolution} at ${price}\n"
                        body_trades += f"  No Probability: {no_prob:.1%}, Expected Value: ${exp_val:.2f}\n\n"
                else:
                    body_trades = "=== NO TRADE RECOMMENDATIONS ===\n"
                    if USE_PROBABILISTIC_APPROACH:
                        body_trades += f"No markets meet minimum expected value threshold of ${MIN_EXPECTED_VALUE}\n\n"
                    else:
                        body_trades += "No markets meet conservative criteria\n\n"

                # Add summary of all market probabilities
                if all_analyses:
                    body_summary = "=== ALL MARKET PROBABILITIES ===\n"
                    # Sort by expected value (descending)
                    all_analyses.sort(key=lambda x: x.get('expected_value', -999), reverse=True)
                    
                    for analysis in all_analyses:
                        body_summary += f"• {analysis['ticker']}: {analysis['condition']}\n"
                        body_summary += f"  No Ask: ${analysis['no_ask']}, No Prob: {analysis['no_probability']:.1%}"
                        if 'expected_value' in analysis:
                            body_summary += f", EV: ${analysis['expected_value']:.2f}"
                        body_summary += "\n\n"
                else:
                    body_summary = ""

                # Prepare temperature log for email body
                body_temp_log = f"=== TEMPERATURE LOG ===\n"
                if temp_data_list:
                    for dt_obj, temp_val in temp_data_list[-100:]:
                        time_str = dt_obj.strftime("%H:%M:%S")
                        highlight = " *** MAX ***" if temp_val == max_temp else ""
                        body_temp_log += f"{time_str}: {temp_val:.2f}°F{highlight}\n"
                else:
                    body_temp_log += "No temperature data available.\n"

                # Combine parts and send email
                full_body = body_intro + body_trades + body_summary + body_temp_log
                if len(alert_list) > 0:
                    send_email(subject, full_body)
            else:
                print("No markets found for analysis.")

    print("\n--- Check complete. ---")