import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Global variable to hold the Firestore client
db = None


def initialize_firebase():
    global db

    # Check if already initialized
    if firebase_admin._apps:
        db = firestore.client()
        return

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

    if cred_json:
        logger.info("Loading Firebase credentials from Environment Variable...")
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    elif os.path.exists(cred_path):
        logger.info(f"Loading Firebase credentials from file: {cred_path}")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    else:
        raise RuntimeError(
            f"Firebase credentials not found. "
            f"Set FIREBASE_CREDENTIALS_JSON env var or provide file at {cred_path}"
        )

    logger.info("Firebase initialized successfully")


def get_db():
    return db
