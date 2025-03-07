import uuid
import kalshi_python
from kalshi_python.models import CreateOrderRequest
from pprint import pprint

import requests

config = kalshi_python.Configuration()
# Comment the line below to use production
# config.host = 'https://demo-api.kalshi.co/trade-api/v2'

# Create an API configuration passing your credentials.
# Use this if you want the kalshi_python sdk to manage the authentication for your.
kalshi_api = kalshi_python.ApiInstance(
    email='r2rhtn57j8@privaterelay.appleid.com',
    password='N@01utter',
    configuration=config,
)

# Optionally you can use the
exchangeStatus = kalshi_api.get_exchange_status()
print('Exchange status response: ')
pprint(exchangeStatus)

# # Gets the data for a specific series.
# seriesTicker = 'FED'
# seriesResponse = kalshi_api.get_series(seriesTicker)
# print('\nSeries: ' + seriesTicker)
# pprint(seriesResponse)

# # Gets the events for a specific series.
# seriesTicker = 'FED'
# eventsResponse = kalshi_api.get_events(series_ticker=seriesTicker,with_nested_markets=True)
# eventsResponse = kalshi_api.get_events()
# print('\nEvents for series: ' + seriesTicker)
# pprint(eventsResponse)

# # Gets the data for a specific event.
# eventTicker = 'INDIACLIMATE-30'
# eventResponse = kalshi_api.get_event(eventTicker)
# print('\nEvent: ' + eventTicker)
# pprint(eventResponse)

# # Get markets
# marketTicker = 'IMOAI-26JAN01'
# marketsResponse = kalshi_api.get_market(ticker=marketTicker)
# # marketsResponse = kalshi_api.get_markets(series="FED")
# print('\nMarkets: ')
# pprint(marketsResponse)

# Gets the orderbook for a specific market.
# marketTicker = 'GTA6-24DEC31'
# orderbookResponse = kalshi_api.get_market_orderbook(ticker=marketTicker)
# print('\nOrderbook for market: ' + marketTicker)
# pprint(orderbookResponse)
