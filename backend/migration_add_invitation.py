from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect, Column, Integer, String
import os

# Initialize Flask app
app = Flask(__name__)
# IMPORTANT: Use the provided path. For a new database, this file might not exist yet.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///aztec.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Define the minimal User model so db.create_all() works ---
class User(db.Model):
    __tablename__ = 'users' 
    id = Column(Integer, primary_key=True)
    # Add a necessary column that would typically be present
    email = Column(String(120), unique=True, nullable=False)
# -------------------------------------------------------------------


def run_migration():
    """Add invitation columns to users table with NOT NULL and UNIQUE constraints"""
    print("Starting migration setup...")
    with app.app_context():
        # This will create the 'users' table (and any others) if the database file is new.
        try:
            db.create_all()
            print("Database initialized: Tables created if missing (based on imported models).")
        except Exception as e:
            print(f"Warning: Could not run db.create_all() completely. Error: {e}")

        try:
            # Check if the 'users' table is actually present
            inspector = inspect(db.engine)
            if 'users' not in inspector.get_table_names():
                print("⚠️ The 'users' table still does not exist. Check that your User model is defined correctly.")
                return

            print("Checking existing columns in 'users' table...")
            
            # Use PRAGMA to get existing columns for SQLite
            result = db.session.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result]
            
            migrations = []
            
            # 1. Add is_invited with NOT NULL constraint
            if 'is_invited' not in columns:
                # SQLite allows adding NOT NULL to new columns with a DEFAULT value
                migrations.append("ALTER TABLE users ADD COLUMN is_invited BOOLEAN DEFAULT 0 NOT NULL")
            
            # 2. Add invitation_token with UNIQUE constraint
            if 'invitation_token' not in columns:
                # SQLite doesn't natively support adding UNIQUE constraints via ALTER TABLE ADD COLUMN.
                # However, for simplicity in this migration script, we'll keep the command as is, 
                # knowing SQLAlchemy/SQLite might require separate index creation for proper UNIQUE enforcement.
                # We handle the index creation below.
                migrations.append("ALTER TABLE users ADD COLUMN invitation_token VARCHAR(100)")
            
            # 3. Add invited_at
            if 'invited_at' not in columns:
                migrations.append("ALTER TABLE users ADD COLUMN invited_at DATETIME")
            
            if not migrations:
                print("✅ All required columns already exist. Migration skipped.")
                # If columns exist, still ensure the index exists
                if 'invitation_token' in columns:
                    db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_invitation_token ON users(invitation_token)"))
                    db.session.commit()
                    print("Index check complete.")
                return

            # Run migrations
            print(f"Found {len(migrations)} missing columns. Applying changes...")
            for migration in migrations:
                print(f"Running: {migration}")
                db.session.execute(text(migration))
            
            # 4. Create index on invitation_token for unique constraint enforcement and faster lookups
            # Note: We enforce the UNIQUE constraint via the index now.
            if 'invitation_token' not in columns:
                 print("Creating UNIQUE index on 'invitation_token'...")
                 # Use the requested index name and add UNIQUE constraint
                 db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_invitation_token ON users(invitation_token)"))

            db.session.commit()
            print("✅ Migration completed successfully!")
            print(f"   Added {len(migrations)} columns and index to users table")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {str(e)}")
            # Raise the exception so the user can see the full traceback if it fails
            raise

if __name__ == '__main__':
    run_migration()