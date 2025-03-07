import csv

# Define the path to the input text file and the output CSV file
input_file_path = 'transactions.txt'
output_file_path = 'transactions.csv'

# Open the input file for reading
with open(input_file_path, 'r') as input_file:
    lines = input_file.readlines()

# Prepare to process the lines and store the processed transactions
transactions = []

# Iterate over each line in the input file
for line in lines:
    # Split the line by multiple spaces to get the fields
    fields = line.split()

    # Check if the line contains a transaction (date field present)
    if len(fields) >= 1 and '/' in fields[0]:
        # Extract fields, handling the narration that might be split across lines
        date = fields[0]
        chq_ref_no = fields[-4]
        value_dt = fields[-3]
        withdrawal_amt = fields[-2] if fields[-2] != '' else '0'
        deposit_amt = fields[-1] if fields[-1] != '' else '0'
        
        # Narration might be split, so we rejoin the parts excluding the last 4 fields and the date
        narration = ' '.join(fields[1:-4])
        
        # Check for continuation of narration in the next line (no date)
        if len(transactions) > 0 and '/' not in transactions[-1][0]:
            transactions[-1][1] += ' ' + narration  # Append the continuation to the last narration
        else:
            # Append the transaction as a new row
            transactions.append([date, narration, chq_ref_no, value_dt, withdrawal_amt, deposit_amt])

# Open the output CSV file for writing
with open(output_file_path, 'w', newline='') as output_file:
    csv_writer = csv.writer(output_file)
    
    # Write the header row
    csv_writer.writerow(['Date', 'Narration', 'Chq./Ref.No.', 'Value Dt', 'Withdrawal Amt.', 'Deposit Amt.', 'Closing Balance'])
    
    # Write the processed transactions to the CSV file
    for transaction in transactions:
        csv_writer.writerow(transaction)

print(f'Transactions have been written to {output_file_path}')
