import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = BASE_DIR / "exports"

DATA_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "tracker.db"

# Paper trading only. Real execution is not implemented.
PAPER_TRADE_CAPITAL_USD = 300.0
TRADING_MODE = "paper"

TRACKED_WALLETS = {
    "AnwrZXy8TdWPivAcPzxhhktsBSgrRA2RREsL8ckQgUv4": "BroadChiefKrill",
    "A1s3dJgS9jaS35pooNSD5Lnyw4bNo3qYgP8wHxUt17xV": "SpareFineBass",
    "9CmNu8kE5j9DPi2T1sCTZvNQULJgU15RpxwWeR8Wme5t": "MidFancyLark",
    "nAWy4pMBkTsVhK6JWGvVm5VKsyxns3sFz4iYGi38qNc": "FreshUpperHyena",
}

# Use the private chat ID or username of the notification bot.
# For private chats, start with the numeric ID if possible.
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

API_ID = os.getenv("TELEGRAM_API_ID", "").strip()
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
PHONE = os.getenv("TELEGRAM_PHONE", "").strip()

SESSION_PATH = str(BASE_DIR / "telegram_user_session")