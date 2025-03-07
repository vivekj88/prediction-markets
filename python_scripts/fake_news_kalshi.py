import requests

# Configuration
FAKE_NEWS_API_URL = "https://fake-news-detection1.p.rapidapi.com/v1/fake_news"
FAKE_NEWS_API_KEY = "e7a09871b0mshf62a47f2c91e475p1630f2jsn3af8dc347672"  # Replace with your RapidAPI key
KALSHI_API_URL = "https://trading-api.kalshi.com/v1/markets"
KALSHI_API_KEY = "your_kalshi_api_key"  # Replace with your Kalshi API key

def detect_fake_news(article_title, article_content):
    """Detects if a news article is fake."""
    headers = {
        "X-RapidAPI-Key": FAKE_NEWS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "title": article_title,
        "content": article_content
    }
    response = requests.post(FAKE_NEWS_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()  # Returns a dictionary with 'fake' or 'real' classification
    else:
        print(f"Error: {response.status_code}")
        return None

def search_kalshi_markets(keywords):
    """Searches Kalshi markets for events matching the given keywords."""
    headers = {"Authorization": f"Bearer {KALSHI_API_KEY}"}
    response = requests.get(KALSHI_API_URL, headers=headers)
    if response.status_code == 200:
        markets = response.json().get("markets", [])
        matching_markets = [
            market for market in markets
            if any(keyword.lower() in market["title"].lower() for keyword in keywords)
        ]
        return matching_markets
    else:
        print(f"Error: {response.status_code}")
        return []

def analyze_news_and_markets(news_articles):
    """Analyzes news articles and finds related Kalshi markets."""
    for article in news_articles:
        title = article.get("title")
        content = article.get("content")
        if not title or not content:
            continue

        # Detect if the news is fake
        detection_result = detect_fake_news(title, content)
        if detection_result and detection_result.get("classification") == "fake":
            print(f"Fake News Detected: {title}")

            # Extract keywords from the title for market search
            keywords = title.split()  # Simple keyword extraction; can be improved
            related_markets = search_kalshi_markets(keywords)

            if related_markets:
                print("Related Kalshi Markets:")
                for market in related_markets:
                    print(f"Market Title: {market['title']}")
                    print(f"Market ID: {market['id']}")
                    print(f"Yes Price: {market['yes_price']}")
                    print(f"No Price: {market['no_price']}")
                    print("Consider the potential impact of this fake news on the market.\n")
            else:
                print("No related markets found on Kalshi.\n")
        else:
            print(f"Article is classified as real: {title}\n")

# Example usage
news_articles = [
    {
        "title": "Major Economic Downturn Expected Next Quarter",
        "content": "Experts predict a significant economic downturn in the upcoming quarter due to various global factors..."
    },
    # Add more articles as needed
]

analyze_news_and_markets(news_articles)
