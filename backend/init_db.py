# File: /backend/init_db.py
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from backend.database import db

def init_database():
    """Initialize the database with all tables and default data"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("🔧 INITIALIZING DATABASE...")
            print("=" * 60)
            
            # Import User model
            from backend.models import User
            
            # Try to import other models if they exist
            try:
                from backend.models import Customer
                has_customer_model = True
            except ImportError:
                has_customer_model = False
                print("⚠️  Customer model not found, skipping...")
            
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # ============================================
            # CREATE DEFAULT USERS
            # ============================================
            user_count = User.query.count()
            if user_count == 0:
                print("\n👤 Creating default users...")
                
                # Create admin user
                admin = User(
                    email='admin@aztecinteriors.com',
                    first_name='Admin',
                    last_name='User',
                    role='Manager',
                    is_active=True,
                    is_verified=True
                )
                admin.set_password('admin123')  # Uses your User model's set_password method
                db.session.add(admin)
                
                # Create test user (from your error message)
                user = User(
                    email='ayaan.ateeb@gmail.com',
                    first_name='Ayaan',
                    last_name='Ateeb',
                    role='Manager',
                    is_active=True,
                    is_verified=True
                )
                user.set_password('Ayaan#1804')  # Uses your User model's set_password method
                db.session.add(user)
                
                # Create employee test user
                employee = User(
                    email='employee@aztecinteriors.com',
                    first_name='Test',
                    last_name='Employee',
                    role='Staff',
                    is_active=True,
                    is_verified=True
                )
                employee.set_password('employee123')  # Uses your User model's set_password method
                db.session.add(employee)
                
                db.session.commit()
                
                print("✅ Default users created:")
                print("   📧 admin@aztecinteriors.com / admin123 (Manager)")
                print("   📧 ayaan.ateeb@gmail.com / Ayaan#1804 (Manager)")
                print("   📧 employee@aztecinteriors.com / employee123 (Staff)")
            else:
                print(f"\n✓ Users already exist ({user_count} users), skipping user creation")
            
            # ============================================
            # CREATE TEST CUSTOMER (if model exists)
            # ============================================
            if has_customer_model:
                from backend.models import Customer
                customer_count = Customer.query.count()
                if customer_count == 0:
                    print("\n🏢 Creating test customer...")
                    test_customer = Customer(
                        name="Test Customer",
                        address="123 Test Street",
                        phone="01234567890",
                        email="test@example.com",
                        status="Active"
                    )
                    db.session.add(test_customer)
                    db.session.commit()
                    print("✅ Test customer created!")
                else:
                    print(f"\n✓ Customers already exist ({customer_count} customers), skipping")
            
            # ============================================
            # VERIFY ALL TABLES
            # ============================================
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print("\n📋 TABLES IN DATABASE:")
            for table in sorted(tables):
                try:
                    count = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    print(f"   ✓ {table} ({count} records)")
                except Exception as e:
                    print(f"   ✓ {table} (unable to count)")
            
            print("\n" + "=" * 60)
            print("✅ DATABASE INITIALIZATION COMPLETE!")
            print("=" * 60)
            print("\n🚀 You can now start the server with: python app.py")
            print("\n📝 LOGIN CREDENTIALS:")
            print("   Admin:    admin@aztecinteriors.com / admin123")
            print("   Manager:  ayaan.ateeb@gmail.com / Ayaan#1804")
            print("   Employee: employee@aztecinteriors.com / employee123")
            print("=" * 60)
                
        except Exception as e:
            print(f"\n❌ Error initializing database: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == "__main__":
    init_database()