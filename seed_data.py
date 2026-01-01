import firebase_admin
from firebase_admin import credentials, firestore
import os
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv

# Load env
load_dotenv()

# Initialize Firebase
cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def seed_data():
    print("🌱 Seeding data...")

    # 1. Create Test Users
    users = [
        {"uid": "user_1", "nickname": "JiuJitsuMaster"},
        {"uid": "user_2", "nickname": "WhiteBeltHero"},
        {"uid": "user_3", "nickname": "MatShark"},
        {"uid": "user_4", "nickname": "GuardPlayer"},
        {"uid": "user_5", "nickname": "KimuraKing"},
    ]

    for u in users:
        db.collection("users").document(u["uid"]).set({
            "uid": u["uid"],
            "nickname": u["nickname"],
            "last_login": firestore.SERVER_TIMESTAMP
        }, merge=True)
    
    print(f"✅ Created {len(users)} users.")

    # 2. Generate Attendance for Past Month (November 2024)
    # now = datetime.now()
    year = 2024
    month = 11
    
    # Get all Saturdays and Sundays in November 2024
    last_day = 30 # Nov has 30 days
    class_days = []
    for day in range(1, last_day + 1):
        d = datetime(year, month, day)
        if d.weekday() in [5, 6]: # Sat(5), Sun(6)
            class_days.append(d)
            
    attendance_ref = db.collection("attendance")
    
    # Clear existing (Optional, but good for clean slate)
    # batch = db.batch()
    # docs = attendance_ref.limit(50).stream()
    # for d in docs:
    #     batch.delete(d.reference)
    # batch.commit()

    count = 0
    
    # Randomly assign attendance
    for day in class_days:
        date_str = day.strftime("%Y-%m-%d")
        
        for user in users:
            # Random chance to attend (80% chance)
            if random.random() < 0.8:
                # Random chance to be late (20% chance if attending)
                is_late = random.random() < 0.2
                status = "late" if is_late else "present"
                point = 5 if is_late else 10
                
                # Set time (13:00 for Sat, 16:00 for Sun approx)
                hour = 13 if day.weekday() == 5 else 16
                minute = random.randint(0, 40)
                attend_time = day.replace(hour=hour, minute=minute, second=0)
                
                doc_id = f"{user['uid']}_{date_str}"
                
                attendance_ref.document(doc_id).set({
                    "user_id": user["uid"],
                    "date": date_str,
                    "timestamp": attend_time,
                    "status": status,
                    "point": point
                })
                count += 1

    print(f"✅ Created {count} attendance records for {len(class_days)} class days.")
    print("Done! Refresh your browser.")

if __name__ == "__main__":
    seed_data()
