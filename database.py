import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Global variable to hold the Firestore client
db = None

def initialize_firebase():
    global db
    
    # Check if already initialized
    if firebase_admin._apps:
        return firestore.client()

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON") # For Cloud Deployment
    
    try:
        if cred_json:
            # Load from Env Var (Best for Render/Cloud)
            print("Loading Firebase credentials from Environment Variable...")
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
        elif os.path.exists(cred_path):
            # Load from File (Local)
            print(f"Loading Firebase credentials from file: {cred_path}")
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
        else:
            print(f"Warning: No Firebase credentials found (File: {cred_path} or Env: FIREBASE_CREDENTIALS_JSON)")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")

def get_db():
    return db
