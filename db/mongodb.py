from dotenv import load_dotenv
from pymongo import MongoClient
import os

load_dotenv()
MONGODB_URI=os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["test"]