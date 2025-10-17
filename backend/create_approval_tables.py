from app import create_app
import sqlite3
from db import get_db_connection

app = create_app()

with app.app_context():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create approval_notifications table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            document_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ Approval notifications table created successfully!")