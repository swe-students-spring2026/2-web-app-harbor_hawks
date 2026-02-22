import os
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]  # repo root
load_dotenv(ROOT / ".env")

_client = None

def get_db():
    global _client
    if _client is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(mongo_uri)
    db_name = os.getenv("DB_NAME", "student_connect")
    return _client[db_name]