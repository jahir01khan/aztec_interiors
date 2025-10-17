# migration_add_approval_fields.py
"""
Migration script to add approval workflow fields to customer_form_data table
Run this once to update your database schema
"""

import sqlite3
from datetime import datetime

def run_migration(db_path='database.db'):
    """
    Add approval workflow columns to customer_form_data table
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Starting migration: Adding approval workflow fields...")
    
    try:
        # 1. Add 'name' column to users table (for convenience)
        print("Adding 'name' column to users table...")
        try:
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN name VARCHAR(100)
            """)
            print("✓ Added 'name' column to users")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ 'name' column already exists in users table")
            else:
                raise
        
        # 2. Add approval_status column
        print("Adding 'approval_status' column to customer_form_data...")
        try:
            cursor.execute("""
                ALTER TABLE customer_form_data 
                ADD COLUMN approval_status VARCHAR(20) DEFAULT 'pending'
            """)
            print("✓ Added 'approval_status' column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ 'approval_status' column already exists")
            else:
                raise
        
        # 3. Add approved_by column
        print("Adding 'approved_by' column to customer_form_data...")
        try:
            cursor.execute("""
                ALTER TABLE customer_form_data 
                ADD COLUMN approved_by INTEGER REFERENCES users(id)
            """)
            print("✓ Added 'approved_by' column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ 'approved_by' column already exists")
            else:
                raise
        
        # 4. Add approval_date column
        print("Adding 'approval_date' column to customer_form_data...")
        try:
            cursor.execute("""
                ALTER TABLE customer_form_data 
                ADD COLUMN approval_date DATETIME
            """)
            print("✓ Added 'approval_date' column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ 'approval_date' column already exists")
            else:
                raise
        
        # 5. Add rejection_reason column
        print("Adding 'rejection_reason' column to customer_form_data...")
        try:
            cursor.execute("""
                ALTER TABLE customer_form_data 
                ADD COLUMN rejection_reason TEXT
            """)
            print("✓ Added 'rejection_reason' column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ 'rejection_reason' column already exists")
            else:
                raise
        
        # 6. Add created_by column
        print("Adding 'created_by' column to customer_form_data...")
        try:
            cursor.execute("""
                ALTER TABLE customer_form_data 
                ADD COLUMN created_by INTEGER REFERENCES users(id)
            """)
            print("✓ Added 'created_by' column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ 'created_by' column already exists")
            else:
                raise
        
        # 7. Update existing records to have 'pending' status
        print("Updating existing records to 'pending' status...")
        cursor.execute("""
            UPDATE customer_form_data 
            SET approval_status = 'pending' 
            WHERE approval_status IS NULL
        """)
        updated_count = cursor.rowcount
        print(f"✓ Updated {updated_count} existing records to 'pending' status")
        
        # 8. Update user names from first_name and last_name
        print("Updating user names...")
        cursor.execute("""
            UPDATE users 
            SET name = first_name || ' ' || last_name 
            WHERE name IS NULL
        """)
        updated_users = cursor.rowcount
        print(f"✓ Updated {updated_users} user names")
        
        # 9. Create indexes for better query performance
        print("Creating indexes for approval queries...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_customer_form_data_approval_status 
                ON customer_form_data(approval_status)
            """)
            print("✓ Created index on approval_status")
        except sqlite3.OperationalError:
            print("⚠ Index on approval_status already exists")
        
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_customer_form_data_created_by 
                ON customer_form_data(created_by)
            """)
            print("✓ Created index on created_by")
        except sqlite3.OperationalError:
            print("⚠ Index on created_by already exists")
        
        # Commit all changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        # Verify the schema
        print("\nVerifying schema changes...")
        cursor.execute("PRAGMA table_info(customer_form_data)")
        columns = cursor.fetchall()
        print("\nCustomer Form Data columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Check if there are any existing records
        cursor.execute("SELECT COUNT(*) FROM customer_form_data")
        count = cursor.fetchone()[0]
        print(f"\nTotal records in customer_form_data: {count}")
        
        if count > 0:
            cursor.execute("""
                SELECT approval_status, COUNT(*) 
                FROM customer_form_data 
                GROUP BY approval_status
            """)
            status_counts = cursor.fetchall()
            print("\nRecords by approval status:")
            for status, cnt in status_counts:
                print(f"  - {status}: {cnt}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        raise
    finally:
        conn.close()
        print("\nDatabase connection closed.")

if __name__ == "__main__":
    # Run the migration
    print("=" * 60)
    print("Customer Form Data - Approval Workflow Migration")
    print("=" * 60)
    print()
    
    try:
        run_migration('database.db')
        print("\n" + "=" * 60)
        print("Migration completed! You can now use the approval workflow.")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print("Migration failed! Please check the error above.")
        print("=" * 60)
        raise