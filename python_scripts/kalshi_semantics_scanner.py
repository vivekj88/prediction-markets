import json
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Load the pre-trained model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Read the JSON file with UTF-8 encoding
with open('all_markets.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Extract text and metadata for all markets
texts = []
metadata = []
for market in data['markets']:
    # Safely get the agency from custom_strike, default to empty string if missing
    agency = market.get('custom_strike', {}).get('Agency', '') if market.get('custom_strike') else ''
    text = f"{market['title']} {market['rules_primary']} {market['rules_secondary']} {agency}"
    texts.append(text)
    metadata.append({
        'ticker': market['ticker'],
        'title': market['title'],
        'agency': agency
    })

# Generate embeddings for all texts
embeddings = model.encode(texts, convert_to_tensor=False)

# Compute pairwise cosine similarity
similarity_matrix = cosine_similarity(embeddings)

# Define a similarity threshold (e.g., 0.9 for "very similar")
threshold = 0.9

# Group similar tickers
visited = set()
similar_groups = []
for i in range(len(similarity_matrix)):
    if i not in visited:
        # Find all tickers similar to ticker i
        similar_indices = [j for j in range(len(similarity_matrix)) if similarity_matrix[i][j] >= threshold and i != j]
        if similar_indices:  # Only include if there are similar tickers
            group = [i] + similar_indices
            similar_groups.append(group)
            visited.update(group)
        else:
            visited.add(i)

# Write to a Markdown file
with open('semantically_similar_tickers.md', 'w', encoding='utf-8') as f:
    if not similar_groups:
        f.write("# No Semantically Similar Tickers Found\n\nNo tickers with a high degree of semantic similarity (threshold 0.9) were identified.")
    else:
        f.write("# Semantically Similar Tickers\n\nThe following groups of tickers are semantically similar based on their titles, rules, and agencies (similarity ≥ 0.9):\n\n")
        for idx, group in enumerate(similar_groups, 1):
            f.write(f"## Group {idx}\n\n")
            f.write(f"- **Number of similar tickers**: {len(group)}\n")
            f.write("- **Tickers and Details**:\n")
            for i in group:
                ticker = metadata[i]['ticker']
                title = metadata[i]['title']
                agency = metadata[i]['agency']
                f.write(f"  - **{ticker}**: {title} (Agency: {agency})\n")
            f.write("\n")

print("Output written to 'semantically_similar_tickers.md'")