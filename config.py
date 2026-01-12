"""
Application configuration.
Loads settings from environment variables or .env file.
"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

# Timezone (env로 덮어쓰기 가능)
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Seoul"))

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
