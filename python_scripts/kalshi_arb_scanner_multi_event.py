import json
from collections import defaultdict
import math

def load_json_file(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def calculate_fee(price_in_cents, num_contracts=1):
    """
    Calculate trading fee in cents: ceil(0.07 * C * P * (1 - P))
    P = price in dollars, C = number of contracts
    """
    p = price_in_cents / 100  # Convert cents to dollars
    fee = 0.07 * num_contracts * p * (1 - p)
    return math.ceil(fee * 100)  # Convert to cents and round up

def find_arbitrage_opportunities(data):
    events = defaultdict(list)
    for market in data['markets']:
        events[market['event_ticker']].append(market)
    
    arbitrage_ops = []
    
    for event_ticker, markets in events.items():
        # Skip if any zero prices
        has_zero_price = any(
            market['yes_ask'] == 0 or 
            market['no_ask'] == 0 or 
            market['yes_bid'] == 0 or 
            market['no_bid'] == 0 
            for market in markets
        )
        if has_zero_price:
            continue
            
        num_markets = len(markets)
        num_contracts = 1  # Default: 1 contract per trade
        
        if num_markets == 1:
            market = markets[0]
            yes_cost = market['yes_ask']
            no_cost = market['no_ask']
            total_cost = yes_cost + no_cost
            yes_fee = calculate_fee(yes_cost, num_contracts)
            no_fee = calculate_fee(no_cost, num_contracts)
            total_fees = yes_fee + no_fee
            total_cost_with_fees = total_cost + total_fees
            if total_cost_with_fees < 100:
                profit = 100 - total_cost_with_fees
                contracts = [
                    {
                        'ticker': market['ticker'],
                        'action': 'buy_yes',
                        'price': yes_cost,
                        'fee': yes_fee,
                        'title': market['title'],
                        'yes_sub_title': market['yes_sub_title'],
                        'no_sub_title': market['no_sub_title'],
                        'expiration_time': market['expiration_time']
                    },
                    {
                        'ticker': market['ticker'],
                        'action': 'buy_no',
                        'price': no_cost,
                        'fee': no_fee,
                        'title': market['title'],
                        'yes_sub_title': market['yes_sub_title'],
                        'no_sub_title': market['no_sub_title'],
                        'expiration_time': market['expiration_time']
                    }
                ]
                arbitrage_ops.append({
                    'event_ticker': event_ticker,
                    'strategy': 'buy_yes_and_no',
                    'contracts': contracts,
                    'total_cost': total_cost,
                    'total_fees': total_fees,
                    'total_cost_with_fees': total_cost_with_fees,
                    'profit': profit,
                    'earliest_expiration': market['expiration_time'],
                    'has_different_expirations': False
                })
                
        elif num_markets > 1:
            # Buy all YES
            total_yes_ask = sum(market['yes_ask'] for market in markets)
            yes_fees = sum(calculate_fee(market['yes_ask'], num_contracts) for market in markets)
            total_yes_cost_with_fees = total_yes_ask + yes_fees
            if total_yes_cost_with_fees < 100:
                profit = 100 - total_yes_cost_with_fees
                contracts = [
                    {
                        'ticker': market['ticker'],
                        'action': 'buy_yes',
                        'price': market['yes_ask'],
                        'fee': calculate_fee(market['yes_ask'], num_contracts),
                        'title': market['title'],
                        'yes_sub_title': market['yes_sub_title'],
                        'no_sub_title': market['no_sub_title'],
                        'expiration_time': market['expiration_time']
                    } for market in markets
                ]
                expiration_times = [c['expiration_time'] for c in contracts]
                earliest_expiration = min(expiration_times)
                has_different_expirations = len(set(expiration_times)) > 1
                arbitrage_ops.append({
                    'event_ticker': event_ticker,
                    'strategy': 'buy_all_yes',
                    'contracts': contracts,
                    'total_cost': total_yes_ask,
                    'total_fees': yes_fees,
                    'total_cost_with_fees': total_yes_cost_with_fees,
                    'profit': profit,
                    'earliest_expiration': earliest_expiration,
                    'has_different_expirations': has_different_expirations
                })
            
            # Buy all NO
            total_no_ask = sum(market['no_ask'] for market in markets)
            no_fees = sum(calculate_fee(market['no_ask'], num_contracts) for market in markets)
            total_no_cost_with_fees = total_no_ask + no_fees
            if total_no_cost_with_fees < 100:
                profit = 100 - total_no_cost_with_fees
                contracts = [
                    {
                        'ticker': market['ticker'],
                        'action': 'buy_no',
                        'price': market['no_ask'],
                        'fee': calculate_fee(market['no_ask'], num_contracts),
                        'title': market['title'],
                        'yes_sub_title': market['yes_sub_title'],
                        'no_sub_title': market['no_sub_title'],
                        'expiration_time': market['expiration_time']
                    } for market in markets
                ]
                expiration_times = [c['expiration_time'] for c in contracts]
                earliest_expiration = min(expiration_times)
                has_different_expirations = len(set(expiration_times)) > 1
                arbitrage_ops.append({
                    'event_ticker': event_ticker,
                    'strategy': 'buy_all_no',
                    'contracts': contracts,
                    'total_cost': total_no_ask,
                    'total_fees': no_fees,
                    'total_cost_with_fees': total_no_cost_with_fees,
                    'profit': profit,
                    'earliest_expiration': earliest_expiration,
                    'has_different_expirations': has_different_expirations
                })
    
    # Sort all opportunities for display
    arbitrage_ops.sort(key=lambda x: (x['has_different_expirations'], x['earliest_expiration']))
    return arbitrage_ops

def save_arbitrage_by_strategy(arbitrage_ops, output_dir='arbitrage'):
    """
    Save arbitrage opportunities into separate files by strategy type.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    strategies = {
        'buy_all_yes': [],
        'buy_all_no': [],
        'buy_yes_and_no': []
    }
    for op in arbitrage_ops:
        strategies[op['strategy']].append(op)
    
    saved_files = []
    for strategy, ops in strategies.items():
        if ops:
            filename = f"{output_dir}/{strategy}.json"
            ops.sort(key=lambda x: (x['has_different_expirations'], x['earliest_expiration']))
            with open(filename, 'w') as f:
                json.dump({'arbitrage_opportunities': ops}, f, indent=4)
            saved_files.append(filename)
    
    return saved_files

def main():
    data = load_json_file('all_markets.json')
    arbitrage_ops = find_arbitrage_opportunities(data)
    
    saved_files = save_arbitrage_by_strategy(arbitrage_ops)
    
    if arbitrage_ops:
        print(f"Found {len(arbitrage_ops)} arbitrage opportunities:")
        for op in arbitrage_ops:
            print(f"\nEvent: {op['event_ticker']}")
            print(f"Strategy: {op['strategy']}")
            print(f"Total Cost: {op['total_cost']} cents")
            print(f"Total Fees: {op['total_fees']} cents")
            print(f"Total Cost with Fees: {op['total_cost_with_fees']} cents")
            print(f"Profit: {op['profit']} cents")
            print(f"Earliest Expiration: {op['earliest_expiration']}")
            print(f"Has Different Expirations: {op['has_different_expirations']}")
            print("Contracts:")
            for contract in op['contracts']:
                print(f"- {contract['action']} {contract['ticker']} @ {contract['price']} cents, Fee: {contract['fee']} cents")
                print(f"  Title: {contract['title']}")
                print(f"  Yes Sub-title: {contract['yes_sub_title']}")
                print(f"  No Sub-title: {contract['no_sub_title']}")
                print(f"  Expiration: {contract['expiration_time']}")
        print(f"\nSaved files: {', '.join(saved_files)}")
    else:
        print("No arbitrage opportunities found.")

if __name__ == "__main__":
    main()