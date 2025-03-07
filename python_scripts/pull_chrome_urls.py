import sqlite3
import os
import shutil
import platform
import sys
from pathlib import Path

def get_chrome_history_path():
    if platform.system() == 'Windows':
        return Path(os.getenv('LOCALAPPDATA')) / 'Google/Chrome/User Data/Default/History'
    elif platform.system() == 'Darwin':  # macOS
        return Path.home() / 'Library/Application Support/Google/Chrome/Default/History'
    elif platform.system() == 'Linux':
        return Path.home() / '.config/google-chrome/Default/History'
    else:
        raise Exception("Unsupported OS")

def fetch_urls_from_history(history_path):
    # Copy history file because SQLite locks it
    temp_history_path = 'chrome_history_copy'
    shutil.copy(history_path, temp_history_path)

    try:
        # Connect to the SQLite database
        connection = sqlite3.connect(temp_history_path)
        cursor = connection.cursor()
        
        # Query to fetch URLs
        cursor.execute('SELECT url FROM urls')
        urls = cursor.fetchall()
        
        return [url[0] for url in urls]
    
    finally:
        connection.close()
        os.remove(temp_history_path)

def save_urls_to_file(urls, filename='chrome_urls.txt'):
    with open(filename, 'w') as file:
        for url in urls:
            file.write(url + '\n')

def main():
    history_path = get_chrome_history_path()
    
    if not os.path.exists(history_path):
        print(f"History file not found at {history_path}")
        sys.exit(1)

    urls = fetch_urls_from_history(history_path)
    save_urls_to_file(urls)
    print(f"URLs have been saved to chrome_urls.txt")

if __name__ == '__main__':
    main()
