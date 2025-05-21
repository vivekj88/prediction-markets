from decimal import Decimal, ROUND_HALF_UP
import math

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