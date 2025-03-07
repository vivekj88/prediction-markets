import json

# Open and read the JSON file
with open('predictit_marketdata.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Open the Markdown file for writing with UTF-8 encoding
with open('predictit_markets.md', 'w', encoding='utf-8') as f:
    for market in data['markets']:
        # Write the market heading as a hyperlink
        f.write(f"# [{market['name']}]({market['url']})\n\n")
        
        # Write market fields (excluding 'contracts')
        for key, value in market.items():
            if key == 'contracts':
                f.write("- **Contracts**:\n")
                for contract in value:
                    f.write(f"  - **{contract['name']}**:\n")
                    for c_key, c_value in contract.items():
                        if c_key != 'name':
                            f.write(f"    - **{c_key}**: {c_value}\n")
            else:
                f.write(f"- **{key}**: {value}\n")
        
        # Add a newline after each market for separation
        f.write("\n")