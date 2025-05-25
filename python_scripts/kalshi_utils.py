from decimal import Decimal, ROUND_HALF_UP
import math
from datetime import datetime, date, timezone, timedelta
import requests
import json

# --- NWS Rounding Function ---
def nws_round(temp_f):
    """Rounds a temperature according to modified NWS rules: midpoints (X.5) round up (toward positive infinity)."""
    if temp_f is None:
        return None
    try:
        # Convert to Decimal for precise arithmetic
        temp_decimal = Decimal(str(temp_f))
        # Extract integer part and fractional part
        integer_part = int(temp_decimal)
        fractional_part = abs(temp_decimal - integer_part)
        # Check if it's a midpoint (X.5)
        if fractional_part == Decimal('0.5'):
            # Round up: add 1 for positive, keep integer_part for negative
            return integer_part + 1 if temp_decimal >= 0 else integer_part
        # For non-midpoint decimals, use standard ROUND_HALF_UP
        return int(temp_decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except Exception as e:
        print(f"Error during NWS rounding for {temp_f}: {e}")
        return math.floor(temp_f)
    

def celsius_to_fahrenheit(celsius):
    """Converts Celsius to Fahrenheit without rounding."""
    if celsius is None:
        return None
    return (celsius * 9 / 5) + 32    


# --- Temperature and Market Logic ---
def get_station_temps_from_api(api_url, target_date_str_to_filter):
    """
    Fetches temperature data from the Mesowest API for the target date.
    Adjusts temperatures on 5-min cadence to lowest unrounded value before finding max,
    handles non-5-min cadence (unrounded Celsius). Converts temperatures to Fahrenheit for output,
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

    for dt_str, temp in zip(dates, air_temps):
        if temp is None:
            continue
        try:
            current_dt_obj = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
            current_date_part = current_dt_obj.date()
            if current_date_part == target_dt_obj:
                float_temp_celsius = float(temp)
                # Check if timestamp is on 5-minute cadence
                is_5min_cadence = current_dt_obj.minute % 5 == 0
                # Adjust temperature if on 5-minute cadence
                if is_5min_cadence:
                    temp_decimal = Decimal(str(float_temp_celsius))
                    integer_part = int(temp_decimal)
                    fractional_part = abs(temp_decimal - integer_part)
                    if fractional_part == Decimal('0.0'):
                        float_temp_celsius = float(temp_decimal - Decimal('0.5'))  # e.g., 32°C → 31.5°C
                    elif fractional_part == Decimal('0.5') and float_temp_celsius < 0:
                        float_temp_celsius = float(temp_decimal - Decimal('0.5'))  # e.g., -3.5°C → -4.0°C
                    elif fractional_part == Decimal('0.5') and float_temp_celsius >= 0:
                        float_temp_celsius = float(temp_decimal)  # e.g., 3.5°C → 3.5°C (already lowest)
                # Store adjusted or original Celsius temperature
                celsius_temps.append(float_temp_celsius)
                # Convert to Fahrenheit for temp_data_list
                temp_data_list.append((current_dt_obj, celsius_to_fahrenheit(float_temp_celsius)))
                # Track latest temperature
                if latest_dt_today is None or current_dt_obj > latest_dt_today:
                    latest_temp_celsius = float_temp_celsius
                    latest_dt_today = current_dt_obj
        except (ValueError, TypeError):
            continue

    if not temp_data_list:
        print(f"No temperature data found for target date {target_date_str_to_filter} in API data (Station TZ: {station_reported_tz}).")
        return None, None, False, [], station_reported_tz

    temp_data_list.sort(key=lambda x: x[0])
    if not celsius_temps:
        print("No valid Celsius temperatures found.")
        return None, None, False, [], station_reported_tz

    max_temp_celsius = max(celsius_temps)

    # Convert max_temp and latest_temp to Fahrenheit
    max_temp_today = celsius_to_fahrenheit(max_temp_celsius)
    latest_temp_today = celsius_to_fahrenheit(latest_temp_celsius) if latest_temp_celsius is not None else None

    # Round max_temp_today using NWS rules
    nws_rounded_max_temp = nws_round(max_temp_today)

    high_temp_reached = (latest_temp_today is not None) and (latest_temp_today < max_temp_today)

    print(f"Data for target date {target_date_str_to_filter}: Max Temp = {max_temp_today:.2f}°F (NWS Rounded: {nws_rounded_max_temp}°F), Latest Temp = {latest_temp_today:.2f}°F (at {latest_dt_today})")
    print(f"Has high temp potentially been reached? {'Yes' if high_temp_reached else 'No'}")

    return max_temp_today, latest_temp_today, high_temp_reached, temp_data_list, station_reported_tz
