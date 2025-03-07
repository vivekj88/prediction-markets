import json
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Load the pre-trained model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Read both JSON files
with open('all_markets.json', 'r', encoding='utf-8') as file:
    all_markets = json.load(file)['markets']

with open('predictit_marketdata.json', 'r', encoding='utf-8') as file:
    predictit_markets = json.load(file)['markets']

# Extract text and metadata for all_markets contracts
all_texts = []
all_metadata = []
for market in all_markets:
    agency = market.get('custom_strike', {}).get('Agency', '') if market.get('custom_strike') else ''
    text = f"{market['title']} {market['rules_primary']} {market['rules_secondary']} {agency}"
    all_texts.append(text)
    all_metadata.append({
        'ticker': market['ticker'],
        'title': market['title'],
        'agency': agency,
        'yes_bid': market['yes_bid'],  # in cents
        'no_bid': market['no_bid']     # in cents
    })

# Extract text and metadata for predictit_markets contracts
predictit_texts = []
predictit_metadata = []
for market in predictit_markets:
    market_name = market['name']
    for contract in market['contracts']:
        text = f"{market_name} {contract['name']}"
        predictit_texts.append(text)
        predictit_metadata.append({
            'market_id': market['id'],
            'contract_id': contract['id'],
            'market_name': market_name,
            'contract_name': contract['name'],
            'yes_bid': contract['bestBuyYesCost'] * 100 if contract['bestBuyYesCost'] is not None else 0,  # Convert $ to cents
            'no_bid': contract['bestBuyNoCost'] * 100 if contract['bestBuyNoCost'] is not None else 0       # Convert $ to cents
        })

# Combine texts and metadata
all_texts_combined = all_texts + predictit_texts
all_metadata_combined = all_metadata + predictit_metadata

# Generate embeddings
embeddings = model.encode(all_texts_combined, convert_to_tensor=False)

# Compute cosine similarity matrix
similarity_matrix = cosine_similarity(embeddings)

# Define similarity threshold
threshold = 0.85

# Find cross-dataset similarities and calculate arbitrage
n_all = len(all_texts)
arbitrage_opportunities = []
for i in range(n_all):  # all_markets indices
    for j in range(n_all, len(all_texts_combined)):  # predictit_markets indices
        if similarity_matrix[i][j] >= threshold:
            all_contract = all_metadata[i]
            predictit_contract = predictit_metadata[j - n_all]
            similarity_score = similarity_matrix[i][j]

            # Calculate arbitrage profit (in cents, assuming $1 = 100 cents payout)
            # Case 1: Buy Yes in all_markets, No in predictit
            cost_yes_all_no_predictit = all_contract['yes_bid'] + predictit_contract['no_bid']
            profit_yes_all_no_predictit = 100 - cost_yes_all_no_predictit if cost_yes_all_no_predictit < 100 else 0

            # Case 2: Buy Yes in predictit, No in all_markets
            cost_yes_predictit_no_all = predictit_contract['yes_bid'] + all_contract['no_bid']
            profit_yes_predictit_no_all = 100 - cost_yes_predictit_no_all if cost_yes_predictit_no_all < 100 else 0

            # Take the maximum profit opportunity
            if profit_yes_all_no_predictit > 0 or profit_yes_predictit_no_all > 0:
                max_profit = max(profit_yes_all_no_predictit, profit_yes_predictit_no_all)
                strategy = "Buy Yes in all_markets, No in predictit" if profit_yes_all_no_predictit >= profit_yes_predictit_no_all else "Buy Yes in predictit, No in all_markets"
                cost = cost_yes_all_no_predictit if strategy == "Buy Yes in all_markets, No in predictit" else cost_yes_predictit_no_all
                arbitrage_opportunities.append({
                    'profit': max_profit,
                    'strategy': strategy,
                    'cost': cost,
                    'similarity': similarity_score,
                    'all_contract': all_contract,
                    'predictit_contract': predictit_contract
                })

# Sort by descending profit
arbitrage_opportunities.sort(key=lambda x: x['profit'], reverse=True)

# Write to Markdown file
with open('arbitrage_opportunities.md', 'w', encoding='utf-8') as f:
    if not arbitrage_opportunities:
        f.write("# No Arbitrage Opportunities Found\n\nNo semantically similar contracts with profitable arbitrage (similarity ≥ 0.85) were identified.")
    else:
        f.write("# Arbitrage Opportunities\n\nThe following semantically similar contracts (similarity ≥ 0.85) offer arbitrage opportunities, sorted by descending profit (assuming $1 payout):\n\n")
        for idx, opp in enumerate(arbitrage_opportunities, 1):
            f.write(f"## Opportunity {idx} (Profit: {opp['profit']} cents)\n\n")
            f.write(f"- **Similarity Score**: {opp['similarity']:.3f}\n")
            f.write(f"- **Strategy**: {opp['strategy']}\n")
            f.write(f"- **Total Cost**: {opp['cost']} cents\n")
            f.write("- **all_markets.json Contract**:\n")
            f.write(f"  - **Ticker**: {opp['all_contract']['ticker']}\n")
            f.write(f"  - **Title**: {opp['all_contract']['title']}\n")
            f.write(f"  - **Agency**: {opp['all_contract']['agency']}\n")
            f.write(f"  - **Yes Bid**: {opp['all_contract']['yes_bid']} cents\n")
            f.write(f"  - **No Bid**: {opp['all_contract']['no_bid']} cents\n")
            f.write("- **predictit_markets.json Contract**:\n")
            f.write(f"  - **Market ID**: {opp['predictit_contract']['market_id']}\n")
            f.write(f"  - **Contract ID**: {opp['predictit_contract']['contract_id']}\n")
            f.write(f"  - **Market Name**: {opp['predictit_contract']['market_name']}\n")
            f.write(f"  - **Contract Name**: {opp['predictit_contract']['contract_name']}\n")
            f.write(f"  - **Yes Bid**: {opp['predictit_contract']['yes_bid']} cents\n")
            f.write(f"  - **No Bid**: {opp['predictit_contract']['no_bid']} cents\n")
            f.write("\n")

print("Output written to 'arbitrage_opportunities.md'")