import requests
import json
import statistics

url = "https://api.elections.kalshi.com/trade-api/v2/markets"
headers = {"accept": "application/json"}
params = {"status": "open"}  # Unix timestamp for March 9, 2025, at 00:00:00 UTC, status set to open

all_markets = []
cursor = None
call_count = 0

for _ in range(150):
    if cursor:
        params["cursor"] = cursor
    
    response = requests.get(url, headers=headers, params=params)
    call_count += 1
    data = response.json()
    
    all_markets.extend(data.get("markets", []))
    cursor = data.get("cursor")
    
    if not cursor:
        break  # Stop if there are no more pages

# Identifying arbitrage opportunities
historical_prices = [market.get("last_price", 0) for market in all_markets if market.get("last_price") is not None]
median_price = statistics.median(historical_prices) if historical_prices else 0

# Initializing filtered market list
positive_ev_markets = []

for market in all_markets:
    open_interest = market.get("open_interest", 0)
    yes_bid = market.get("yes_bid", 0)
    yes_ask = market.get("yes_ask", 0)
    no_bid = market.get("no_bid", 0)
    no_ask = market.get("no_ask", 0)
    last_price = market.get("last_price", 0)
    
    # Ensure valid bid/ask values
    if open_interest > 10 and yes_bid > 0 and yes_ask > 0 and no_bid > 0 and no_ask > 0:
        
        # Calculate probabilities for "Yes" and "No" outcomes
        total_bid_ask_yes = yes_bid + no_bid
        total_bid_ask_no = yes_ask + no_ask
        
        prob_yes = yes_bid / total_bid_ask_yes if total_bid_ask_yes > 0 else 0
        prob_no = no_bid / total_bid_ask_no if total_bid_ask_no > 0 else 0
        
        # Calculate expected value for "Yes" outcome
        ev_yes = (prob_yes * 100) - yes_ask  # Expected value for "Yes"
        
        # Calculate expected value for "No" outcome
        ev_no = (prob_no * 100) - no_ask  # Expected value for "No"
        
        # If either "Yes" or "No" has a positive expected value, consider this market
        if ev_yes > 0 or ev_no > 0:
            positive_ev_markets.append(market)

# Write positive expected value markets to a file
with open("positive_ev_markets.json", "w", encoding="utf-8") as file:
    json.dump({"markets": positive_ev_markets}, file, indent=4)

print("Filtered positive expected value markets saved to positive_ev_markets.json")
print(f"Total API calls made: {call_count}")
