import requests
import json
import statistics

url = "https://api.elections.kalshi.com/trade-api/v2/markets"
headers = {"accept": "application/json"}
params = {"status": "open"}  # Unix timestamp for March 9, 2025, at 00:00:00 UTC, status set to open

all_markets = []
cursor = None
call_count = 0

for _ in range(1500):
    if cursor:
        params["cursor"] = cursor
    
    response = requests.get(url, headers=headers, params=params)
    call_count += 1
    data = response.json()
    
    all_markets.extend(data.get("markets", []))
    cursor = data.get("cursor")
    
    if not cursor:
        break  # Stop if there are no more pages

# Initializing filtered market lists for each criterion
bid_ask_mismatch_markets = []
liquid_markets = []

for market in all_markets:
    open_interest = market.get("open_interest", 0)
    yes_bid = market.get("yes_bid", 0)
    yes_ask = market.get("yes_ask", 0)
    no_bid = market.get("no_bid", 0)
    no_ask = market.get("no_ask", 0)
    last_price = market.get("last_price", 0)
    
    # Ensure valid bid/ask values
    if open_interest > 0 and yes_bid > 0 and yes_ask > 0 and no_bid > 0 and no_ask > 0:

        liquid_markets.append(market)
        # Check bid-ask sum mismatch
        if (no_bid + yes_ask != 100) or (yes_bid + no_ask != 100):
            bid_ask_mismatch_markets.append(market)

# Write each filter's results to separate files
with open("bid_ask_mismatch_markets.json", "w", encoding="utf-8") as file:
    json.dump({"markets": bid_ask_mismatch_markets}, file, indent=4)

with open("liquid_markets.json", "w", encoding="utf-8") as file:
    json.dump({"markets": liquid_markets}, file, indent=4)

with open("all_markets.json", "w", encoding="utf-8") as file:
    json.dump({"markets": all_markets}, file, indent=4)

print(f"Total API calls made: {call_count}")
