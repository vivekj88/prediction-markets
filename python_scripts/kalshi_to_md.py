import json

# Open and read the JSON file
with open('all_markets.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Open the Markdown file for writing
with open('kalshi_markets.md', 'w', encoding='utf-8') as f:
    # Iterate through each market in the 'markets' array
    for market in data['markets']:
        # Write the ticker as a heading
        f.write(f"# {market['ticker']}\n\n")
        
        # Write all other fields as bullet points, excluding 'ticker'
        for key, value in market.items():
            if key != 'ticker':
                f.write(f"- **{key}**: {value}\n")
        
        # Add a newline after each market's section for separation
        f.write("\n")