import requests
import json

# Define the API endpoint URL
url = 'https://www.predictit.org/api/marketdata/all/'

# Indicate that the script is fetching data
print("Fetching data from", url)

# Make a GET request to the API
response = requests.get(url)

# Check if the request was successful (status code 200)
if response.status_code == 200:
    try:
        # Parse the response into JSON format (converts it into a Python dictionary)
        data = response.json()
        
        # Open a file in write mode and write the JSON data with indentation
        with open('predictit_marketdata.json', 'w') as file:
            json.dump(data, file, indent=4)
        
        # Confirm that the data has been written
        print("Data written to marketdata.json")
    except json.JSONDecodeError:
        # Handle the case where the response is not valid JSON
        print("Response is not valid JSON")
else:
    # Handle the case where the request fails
    print("Failed to fetch data. Status code:", response.status_code)