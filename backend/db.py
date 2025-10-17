# db.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Create and return a SQLite database connection for raw queries"""
    try:
        db_path = os.getenv('DATABASE_PATH', 'database.db')
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row  # Access columns by name like dictionary
        return connection
    except sqlite3.Error as err:
        print(f"Database connection error: {err}")
        raise