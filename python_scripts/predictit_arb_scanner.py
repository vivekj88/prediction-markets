import json
from collections import defaultdict

def load_json_file(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def find_arbitrage_opportunities(data):
    arbitrage_ops = []
    
    for market in data['markets']:
        market_id = market['id']
        contracts = market['contracts']
        num_contracts = len(contracts)
        
        # Convert prices to cents and handle nulls
        for contract in contracts:
            contract['bestBuyYesCost'] = int(contract['bestBuyYesCost'] * 100) if contract['bestBuyYesCost'] is not None else None
            contract['bestBuyNoCost'] = int(contract['bestBuyNoCost'] * 100) if contract['bestBuyNoCost'] is not None else None
        
        # Skip if any contract has null or zero prices
        has_invalid_price = any(
            c['bestBuyYesCost'] is None or c['bestBuyNoCost'] is None or 
            c['bestBuyYesCost'] == 0 or c['bestBuyNoCost'] == 0 
            for c in contracts
        )
        if has_invalid_price:
            continue
        
        if num_contracts == 1:
            # Single contract: check buy_yes_and_no
            contract = contracts[0]
            yes_cost = contract['bestBuyYesCost']
            no_cost = contract['bestBuyNoCost']
            total_cost = yes_cost + no_cost
            if total_cost < 100:  # Less than $1 payout
                profit_before_fee = 100 - total_cost
                fee = int(profit_before_fee * 0.10)  # 10% fee on profit
                profit = profit_before_fee - fee
                if profit > 0:
                    contracts_data = [
                        {
                            'id': contract['id'],
                            'action': 'buy_yes',
                            'price': yes_cost,
                            'name': contract['name'],
                            'shortName': contract['shortName'],
                            'dateEnd': contract['dateEnd']
                        },
                        {
                            'id': contract['id'],
                            'action': 'buy_no',
                            'price': no_cost,
                            'name': contract['name'],
                            'shortName': contract['shortName'],
                            'dateEnd': contract['dateEnd']
                        }
                    ]
                    arbitrage_ops.append({
                        'market_id': market_id,
                        'market_name': market['name'],
                        'strategy': 'buy_yes_and_no',
                        'contracts': contracts_data,
                        'total_cost': total_cost,
                        'profit_before_fee': profit_before_fee,
                        'fee': fee,
                        'profit': profit,
                        'earliest_expiration': contract['dateEnd'],
                        'has_different_expirations': False
                    })
        
        elif num_contracts > 1:
            # Multi-contract market: check buy_all_yes and buy_all_no
            total_yes_cost = sum(c['bestBuyYesCost'] for c in contracts)
            total_no_cost = sum(c['bestBuyNoCost'] for c in contracts)
            
            # Buy all YES
            if total_yes_cost < 100:
                profit_before_fee = 100 - total_yes_cost
                fee = int(profit_before_fee * 0.10)
                profit = profit_before_fee - fee
                if profit > 0:
                    contracts_data = [
                        {
                            'id': c['id'],
                            'action': 'buy_yes',
                            'price': c['bestBuyYesCost'],
                            'name': c['name'],
                            'shortName': c['shortName'],
                            'dateEnd': c['dateEnd']
                        } for c in contracts
                    ]
                    expiration_times = [c['dateEnd'] for c in contracts]
                    earliest_expiration = min(expiration_times) if 'NA' not in expiration_times else 'NA'
                    has_different_expirations = len(set(expiration_times)) > 1 and 'NA' not in expiration_times
                    arbitrage_ops.append({
                        'market_id': market_id,
                        'market_name': market['name'],
                        'strategy': 'buy_all_yes',
                        'contracts': contracts_data,
                        'total_cost': total_yes_cost,
                        'profit_before_fee': profit_before_fee,
                        'fee': fee,
                        'profit': profit,
                        'earliest_expiration': earliest_expiration,
                        'has_different_expirations': has_different_expirations
                    })
            
            # Buy all NO
            if total_no_cost < 100:
                profit_before_fee = 100 - total_no_cost
                fee = int(profit_before_fee * 0.10)
                profit = profit_before_fee - fee
                if profit > 0:
                    contracts_data = [
                        {
                            'id': c['id'],
                            'action': 'buy_no',
                            'price': c['bestBuyNoCost'],
                            'name': c['name'],
                            'shortName': c['shortName'],
                            'dateEnd': c['dateEnd']
                        } for c in contracts
                    ]
                    expiration_times = [c['dateEnd'] for c in contracts]
                    earliest_expiration = min(expiration_times) if 'NA' not in expiration_times else 'NA'
                    has_different_expirations = len(set(expiration_times)) > 1 and 'NA' not in expiration_times
                    arbitrage_ops.append({
                        'market_id': market_id,
                        'market_name': market['name'],
                        'strategy': 'buy_all_no',
                        'contracts': contracts_data,
                        'total_cost': total_no_cost,
                        'profit_before_fee': profit_before_fee,
                        'fee': fee,
                        'profit': profit,
                        'earliest_expiration': earliest_expiration,
                        'has_different_expirations': has_different_expirations
                    })
    
    # Sort: uniform expirations first, then earliest_expiration (handle 'NA')
    arbitrage_ops.sort(key=lambda x: (x['has_different_expirations'], x['earliest_expiration'] if x['earliest_expiration'] != 'NA' else 'Z'))
    return arbitrage_ops

def save_arbitrage_by_strategy(arbitrage_ops, output_dir='predictit_arbitrage'):
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
            ops.sort(key=lambda x: (x['has_different_expirations'], x['earliest_expiration'] if x['earliest_expiration'] != 'NA' else 'Z'))
            with open(filename, 'w') as f:
                json.dump({'arbitrage_opportunities': ops}, f, indent=4)
            saved_files.append(filename)
    
    return saved_files

def main():
    data = load_json_file('predictit_marketdata.json')
    arbitrage_ops = find_arbitrage_opportunities(data)
    
    saved_files = save_arbitrage_by_strategy(arbitrage_ops)
    
    if arbitrage_ops:
        print(f"Found {len(arbitrage_ops)} arbitrage opportunities:")
        for op in arbitrage_ops:
            print(f"\nMarket ID: {op['market_id']}")
            print(f"Market Name: {op['market_name']}")
            print(f"Strategy: {op['strategy']}")
            print(f"Total Cost: {op['total_cost']} cents")
            print(f"Profit Before Fee: {op['profit_before_fee']} cents")
            print(f"Fee (10%): {op['fee']} cents")
            print(f"Net Profit: {op['profit']} cents")
            print(f"Earliest Expiration: {op['earliest_expiration']}")
            print(f"Has Different Expirations: {op['has_different_expirations']}")
            print("Contracts:")
            for contract in op['contracts']:
                print(f"- {contract['action']} {contract['id']} @ {contract['price']} cents")
                print(f"  Name: {contract['name']}")
                print(f"  Short Name: {contract['shortName']}")
                print(f"  Expiration: {contract['dateEnd']}")
        print(f"\nSaved files: {', '.join(saved_files)}")
    else:
        print("No arbitrage opportunities found.")

if __name__ == "__main__":
    main()