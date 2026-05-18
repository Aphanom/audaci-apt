import os
from dotenv import load_dotenv

load_dotenv()

print(f"TELEGRAM_TOKEN: {os.getenv('TELEGRAM_TOKEN')}")
print(f"LASTFM_API_KEY: {os.getenv('LASTFM_API_KEY')}")
