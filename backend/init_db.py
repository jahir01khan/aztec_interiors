# File: /backend/init_db.py
import sys
import os

# Add parent directory to path so we can import app and backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.db import Base, engine, SessionLocal
from backend.models import User  # Import your ORM models directly here

def init_database():
    """Initialize the database with all tables and default data"""
    try:
        print("=" * 60)
        print("🔧 INITIALIZING DATABASE...")
        print("=" * 60)

        # Create all tables based on your models
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables verified/created successfully!")

        # Start a session
        session = SessionLocal()

        # Check if users exist
        user_count = session.query(User).count()
        if user_count == 0:
            print("\n👤 Creating default users...")

            admin = User(
                email='admin@aztecinteriors.com',
                first_name='Admin',
                last_name='User',
                role='Manager',
                is_active=True,
                is_verified=True
            )
            admin.set_password('admin123')

            manager = User(
                email='ayaan.ateeb@gmail.com',
                first_name='Ayaan',
                last_name='Ateeb',
                role='Manager',
                is_active=True,
                is_verified=True
            )
            manager.set_password('Ayaan#1804')

            employee = User(
                email='employee@aztecinteriors.com',
                first_name='Test',
                last_name='Employee',
                role='Staff',
                is_active=True,
                is_verified=True
            )
            employee.set_password('employee123')

            session.add_all([admin, manager, employee])
            session.commit()

            print("✅ Default users created successfully!")

        else:
            print(f"\n✓ Users already exist ({user_count} users), skipping user creation")

        print("\n✅ DATABASE INITIALIZATION COMPLETE!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    init_database()
