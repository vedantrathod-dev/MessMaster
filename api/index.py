import os
import sys

# Add parent directory to sys.path so modules like app and database can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import database
from app import app

# Initialize database on cold boot if needed
try:
    database.init_db(seed_sample=False)
    database.update_all_mess_expiries()
except Exception as e:
    print(f"Database boot warning: {e}")

# Vercel entrypoint expects 'app'
if __name__ == '__main__':
    app.run()
