import json
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import math

# Load the pre-trained model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Read both JSON files
with open('all_markets.json', 'r', encoding='utf-8') as file:
    all_markets = json.load(file)['markets']

with open('predictit_marketdata.json', 'r', encoding='utf-8') as file:
    predictit_markets = json.load(file)['markets']

def calculate_kalshi_fee(price_in_dollars, num_contracts=100):
    """Calculate Kalshi trading fee in dollars for num_contracts: ceil(0.07 * C * P * (1 - P))"""
    fee = 0.07 * num_contracts * price_in_dollars * (1 - price_in_dollars)
    return math.ceil(fee * 100) / 100  # Round up to 2 decimal places

# Extract text and metadata for Kalshi contracts (convert to dollars)
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
        'yes_bid': market['yes_bid'] / 100,
        'no_bid': market['no_bid'] / 100,
        'yes_ask': market['yes_ask'] / 100,
        'no_ask': market['no_ask'] / 100,
        'expiration_time': market['expiration_time']  # Add expiration time
    })

# Extract text and metadata for PredictIt contracts (already in dollars)
predictit_texts = []
predictit_metadata = []
for market in predictit_markets:
    market_name = market['name']
    for contract in market['contracts']:
        text = f"{market_name} {contract['name']}"
        predictit_texts.append(text)
        yes_bid = contract['bestBuyYesCost'] if contract['bestBuyYesCost'] is not None else 0
        no_bid = contract['bestBuyNoCost'] if contract['bestBuyNoCost'] is not None else 0
        predictit_metadata.append({
            'market_id': market['id'],
            'contract_id': contract['id'],
            'market_name': market_name,
            'contract_name': contract['name'],
            'yes_bid': yes_bid,
            'no_bid': no_bid,
            'dateEnd': contract['dateEnd']  # Add expiration date
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

# Find cross-dataset similarities and calculate arbitrage with fees in dollars for 100 contracts
n_all = len(all_texts)
arbitrage_opportunities = []
for i in range(n_all):
    for j in range(n_all, len(all_texts_combined)):
        if similarity_matrix[i][j] >= threshold:
            kalshi_contract = all_metadata[i]
            predictit_contract = predictit_metadata[j - n_all]
            similarity_score = similarity_matrix[i][j]

            # Case 1: Buy Yes in Kalshi, No in PredictIt (100 contracts)
            kalshi_yes_cost_per = kalshi_contract['yes_ask']
            predictit_no_cost_per = predictit_contract['no_bid']
            kalshi_yes_cost = kalshi_yes_cost_per * 100
            predictit_no_cost = predictit_no_cost_per * 100
            kalshi_yes_fee = calculate_kalshi_fee(kalshi_yes_cost_per, 100)
            total_cost_yes_kalshi_no_predictit = kalshi_yes_cost + predictit_no_cost + kalshi_yes_fee
            if total_cost_yes_kalshi_no_predictit < 100.0:
                profit_before_predictit_fee = 100.0 - total_cost_yes_kalshi_no_predictit
                predictit_fee = profit_before_predictit_fee * 0.10
                net_profit = profit_before_predictit_fee - predictit_fee
                if net_profit > 0:
                    kalshi_profit = 100.0 - kalshi_yes_cost - kalshi_yes_fee - predictit_no_cost - predictit_fee
                    predictit_profit = 100.0 - predictit_no_cost - kalshi_yes_cost - kalshi_yes_fee - predictit_fee
                    arbitrage_opportunities.append({
                        'profit': net_profit,
                        'strategy': "Buy Yes in Kalshi, No in PredictIt",
                        'cost': kalshi_yes_cost + predictit_no_cost,
                        'kalshi_fee': kalshi_yes_fee,
                        'predictit_fee': predictit_fee,
                        'total_cost_with_fees': total_cost_yes_kalshi_no_predictit,
                        'kalshi_profit': kalshi_profit,
                        'predictit_profit': predictit_profit,
                        'similarity': similarity_score,
                        'kalshi_contract': kalshi_contract,
                        'predictit_contract': predictit_contract
                    })

            # Case 2: Buy Yes in PredictIt, No in Kalshi (100 contracts)
            predictit_yes_cost_per = predictit_contract['yes_bid']
            kalshi_no_cost_per = kalshi_contract['no_ask']
            predictit_yes_cost = predictit_yes_cost_per * 100
            kalshi_no_cost = kalshi_no_cost_per * 100
            kalshi_no_fee = calculate_kalshi_fee(kalshi_no_cost_per, 100)
            total_cost_yes_predictit_no_kalshi = predictit_yes_cost + kalshi_no_cost + kalshi_no_fee
            if total_cost_yes_predictit_no_kalshi < 100.0:
                profit_before_predictit_fee = 100.0 - total_cost_yes_predictit_no_kalshi
                predictit_fee = profit_before_predictit_fee * 0.10
                net_profit = profit_before_predictit_fee - predictit_fee
                if net_profit > 0:
                    predictit_profit = 100.0 - predictit_yes_cost - kalshi_no_cost - kalshi_no_fee - predictit_fee
                    kalshi_profit = 100.0 - kalshi_no_cost - predictit_yes_cost - kalshi_no_fee - predictit_fee
                    arbitrage_opportunities.append({
                        'profit': net_profit,
                        'strategy': "Buy Yes in PredictIt, No in Kalshi",
                        'cost': predictit_yes_cost + kalshi_no_cost,
                        'kalshi_fee': kalshi_no_fee,
                        'predictit_fee': predictit_fee,
                        'total_cost_with_fees': total_cost_yes_predictit_no_kalshi,
                        'kalshi_profit': kalshi_profit,
                        'predictit_profit': predictit_profit,
                        'similarity': similarity_score,
                        'kalshi_contract': kalshi_contract,
                        'predictit_contract': predictit_contract
                    })

# Sort by descending profit
arbitrage_opportunities.sort(key=lambda x: x['profit'], reverse=True)

# Write to Markdown file
with open('arbitrage_opportunities.md', 'w', encoding='utf-8') as f:
    if not arbitrage_opportunities:
        f.write("# No Arbitrage Opportunities Found\n\nNo semantically similar contracts with profitable arbitrage (similarity ≥ 0.85) were identified after accounting for fees.")
    else:
        f.write("# Arbitrage Opportunities\n\nThe following semantically similar contracts (similarity ≥ 0.85) offer arbitrage opportunities for 100 contracts after accounting for Kalshi (7% trading) and PredictIt (10% profit) fees, sorted by descending net profit (assuming $1 payout per contract):\n\n")
        for idx, opp in enumerate(arbitrage_opportunities, 1):
            f.write(f"## Opportunity {idx} (Net Profit: ${opp['profit']:.2f})\n\n")
            f.write(f"- **Similarity Score**: {opp['similarity']:.3f}\n")
            f.write(f"- **Strategy**: {opp['strategy']}\n")
            f.write(f"- **Base Cost**: ${opp['cost']:.2f}\n")
            f.write(f"- **Kalshi Fee**: ${opp['kalshi_fee']:.2f}\n")
            f.write(f"- **PredictIt Fee (10% of Profit)**: ${opp['predictit_fee']:.2f}\n")
            f.write(f"- **Total Cost with Fees**: ${opp['total_cost_with_fees']:.2f}\n")
            f.write(f"- **Profit if Kalshi Pays Out**: ${opp['kalshi_profit']:.2f}\n")
            f.write(f"- **Profit if PredictIt Pays Out**: ${opp['predictit_profit']:.2f}\n")
            f.write("- **Kalshi Contract**:\n")
            f.write(f"  - **Ticker**: {opp['kalshi_contract']['ticker']}\n")
            f.write(f"  - **Title**: {opp['kalshi_contract']['title']}\n")
            f.write(f"  - **Agency**: {opp['kalshi_contract']['agency']}\n")
            f.write(f"  - **Yes Ask**: ${opp['kalshi_contract']['yes_ask']:.2f}\n")
            f.write(f"  - **No Ask**: ${opp['kalshi_contract']['no_ask']:.2f}\n")
            f.write(f"  - **Expiration Time**: {opp['kalshi_contract']['expiration_time']}\n")
            f.write("- **PredictIt Contract**:\n")
            f.write(f"  - **Market ID**: {opp['predictit_contract']['market_id']}\n")
            f.write(f"  - **Contract ID**: {opp['predictit_contract']['contract_id']}\n")
            f.write(f"  - **Market Name**: {opp['predictit_contract']['market_name']}\n")
            f.write(f"  - **Contract Name**: {opp['predictit_contract']['contract_name']}\n")
            f.write(f"  - **Yes Bid**: ${opp['predictit_contract']['yes_bid']:.2f}\n")
            f.write(f"  - **No Bid**: ${opp['predictit_contract']['no_bid']:.2f}\n")
            f.write(f"  - **Expiration Date**: {opp['predictit_contract']['dateEnd']}\n")
            f.write("\n")

print("Output written to 'arbitrage_opportunities.md'")