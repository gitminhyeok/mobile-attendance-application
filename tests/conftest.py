import os
import sys

# dependencies.py refuses to import without SECRET_KEY (by design)
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_UID", "admin-uid-1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
