import firebase_admin
from firebase_admin import credentials, firestore
import os
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
    
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print(f"Firebase initialized using {cred_path}")
    else:
        print(f"Warning: Firebase credentials not found at {cred_path}. Firestore will not work.")
        # For development without keys, you might want to mock db or raise error
        # db = MockFirestore() 
        pass

def get_db():
    return db
