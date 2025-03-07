import json

def read_input_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def find_arbitrage_opportunities(data):
    arbitrage_opportunities = []

    # Loop through each market individually
    for market in data["markets"]:

        yes_bid = market["yes_bid"]
        yes_ask = market["yes_ask"]
        no_bid = market["no_bid"]
        no_ask = market["no_ask"]

        # Check for 'buy both' arbitrage
        if yes_ask + no_ask < 100:
            potential_profit = 100 - (yes_ask + no_ask)
            opportunity = market.copy()
            opportunity["arbitrage_type"] = "buy_both"
            opportunity["potential_profit"] = potential_profit
            arbitrage_opportunities.append(opportunity)
        # Check for 'sell both' arbitrage
        elif yes_bid + no_bid > 100:
            potential_profit = (yes_bid + no_bid) - 100
            opportunity = market.copy()
            opportunity["arbitrage_type"] = "sell_both"
            opportunity["potential_profit"] = potential_profit
            arbitrage_opportunities.append(opportunity)
    
    return arbitrage_opportunities

def write_output_file(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

# Input file path (change to your actual input file path)
input_file_path = 'all_markets.json'
# Output file path (change to where you want to store the result)
output_file_path = 'arbitrage_opportunities.json'

# Read input data from the file
data = read_input_file(input_file_path)

# Find arbitrage opportunities
arbitrage_opportunities = find_arbitrage_opportunities(data)

# Prepare filtered data
filtered_data = {
    "arbitrage_opportunities": arbitrage_opportunities
}

# Write filtered arbitrage opportunities to the output file
write_output_file(output_file_path, filtered_data)
print(f"count of arbitrage opportunities: {len(arbitrage_opportunities)}")
