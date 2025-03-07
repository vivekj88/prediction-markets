# Script to check for arbitrage opportunities in two binary options markets
# Assumptions: 
# - Both markets are for the same underlying event
# - Payout is $100 if the contract condition is met
# - Ask prices are in dollars

print("Enter the ask prices for yes and no contracts in both markets (in dollars).")

try:
    # Get input from the user for ask prices
    ask_yes_A = float(input("Ask price for yes in market A: "))
    ask_no_A = float(input("Ask price for no in market A: "))
    ask_yes_B = float(input("Ask price for yes in market B: "))
    ask_no_B = float(input("Ask price for no in market B: "))

    # List to store arbitrage opportunities
    opportunities = []

    # Check cross-market strategy 1: Buy yes from market B and no from market A
    if ask_yes_B + ask_no_A < 100:
        profit = 100 - (ask_yes_B + ask_no_A)
        opportunities.append(f"Buy yes from market B and no from market A, profit: ${profit:.2f}")

    # Check cross-market strategy 2: Buy yes from market A and no from market B
    if ask_yes_A + ask_no_B < 100:
        profit = 100 - (ask_yes_A + ask_no_B)
        opportunities.append(f"Buy yes from market A and no from market B, profit: ${profit:.2f}")

    # Check within-market strategy for market A: Buy both yes and no
    if ask_yes_A + ask_no_A < 100:
        profit = 100 - (ask_yes_A + ask_no_A)
        opportunities.append(f"Buy yes and no from market A, profit: ${profit:.2f}")

    # Check within-market strategy for market B: Buy both yes and no
    if ask_yes_B + ask_no_B < 100:
        profit = 100 - (ask_yes_B + ask_no_B)
        opportunities.append(f"Buy yes and no from market B, profit: ${profit:.2f}")

    # Output results
    if opportunities:
        print("Arbitrage opportunity exists:")
        for opportunity in opportunities:
            print(opportunity)
    else:
        print("No arbitrage opportunity exists.")

except ValueError:
    print("Invalid input. Please enter numerical values for the ask prices.")