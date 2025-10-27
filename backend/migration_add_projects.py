import sqlite3
from datetime import datetime
import uuid

def run_migration(db_path='database.db'):
    """
    Add projects table and approval workflow columns
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Starting migration: Adding projects and approval workflow...")
    
    try:
        # ==========================================
        # PART 1: CREATE PROJECTS TABLE
        # ==========================================
        print("\n" + "="*60)
        print("PART 1: Creating Projects Table")
        print("="*60)
        
        print("Creating 'projects' table...")
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id VARCHAR(36) PRIMARY KEY,
                    customer_id VARCHAR(36) NOT NULL,
                    project_name VARCHAR(255) NOT NULL,
                    project_type VARCHAR(50) NOT NULL,
                    stage VARCHAR(50) NOT NULL DEFAULT 'Lead',
                    date_of_measure DATE,
                    notes TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (updated_by) REFERENCES users(id)
                )
            """)
            print("✓ Created 'projects' table")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print("⚠ 'projects' table already exists")
            else:
                raise
        
        # Create indexes for projects
        print("Creating indexes for projects table...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_customer_id 
                ON projects(customer_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_stage 
                ON projects(stage)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_type 
                ON projects(project_type)
            """)
            print("✓ Created indexes for projects")
        except sqlite3.OperationalError as e:
            print(f"⚠ Some indexes already exist: {e}")
        
        # ==========================================
        # PART 2: ADD PROJECT_ID TO CUSTOMER_FORM_DATA
        # ==========================================
        print("\n" + "="*60)
        print("PART 2: Linking Forms to Projects")
        print("="*60)
        
        print("Adding 'project_id' column to customer_form_data...")
        try:
            cursor.execute("""
                ALTER TABLE customer_form_data 
                ADD COLUMN project_id VARCHAR(36)
            """)
            print("✓ Added 'project_id' column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ 'project_id' column already exists")
            else:
                raise
        
        # Create index for project_id
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_customer_form_data_project_id 
                ON customer_form_data(project_id)
            """)
            print("✓ Created index on project_id")
        except sqlite3.OperationalError:
            print("⚠ Index on project_id already exists")
        
        # ==========================================
        # PART 3: MIGRATE EXISTING CUSTOMERS TO PROJECTS
        # ==========================================
        print("\n" + "="*60)
        print("PART 3: Migrating Existing Customers")
        print("="*60)
        
        # Check if customers exist
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        print(f"Found {customer_count} existing customers")
        
        if customer_count > 0:
            # Check if any projects already exist
            cursor.execute("SELECT COUNT(*) FROM projects")
            existing_projects = cursor.fetchone()[0]
            
            if existing_projects == 0:
                print("Creating default project for each customer...")
                
                # Get all customers
                cursor.execute("""
                    SELECT id, name, stage, date_of_measure, created_by, created_at 
                    FROM customers
                """)
                customers = cursor.fetchall()
                
                projects_created = 0
                for customer in customers:
                    customer_id, name, stage, date_of_measure, created_by, created_at = customer
                    
                    # Create a default project for this customer
                    project_id = str(uuid.uuid4())
                    project_name = f"{name}'s Project"
                    project_type = "Other"  # Default type
                    project_stage = stage if stage else "Lead"
                    
                    cursor.execute("""
                        INSERT INTO projects (
                            id, customer_id, project_name, project_type, 
                            stage, date_of_measure, notes, created_by, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        project_id, customer_id, project_name, project_type,
                        project_stage, date_of_measure, 
                        "Migrated from customer record", created_by, created_at
                    ))
                    
                    # Link all existing forms to this project
                    cursor.execute("""
                        UPDATE customer_form_data 
                        SET project_id = ? 
                        WHERE customer_id = ? AND project_id IS NULL
                    """, (project_id, customer_id))
                    
                    projects_created += 1
                
                print(f"✓ Created {projects_created} default projects")
                
                # Check how many forms were linked
                cursor.execute("""
                    SELECT COUNT(*) FROM customer_form_data WHERE project_id IS NOT NULL
                """)
                linked_forms = cursor.fetchone()[0]
                print(f"✓ Linked {linked_forms} forms to projects")
            else:
                print(f"⚠ {existing_projects} projects already exist, skipping migration")
        
        # ==========================================
        # PART 4: ADD APPROVAL WORKFLOW FIELDS
        # ==========================================
        print("\n" + "="*60)
        print("PART 4: Adding Approval Workflow Fields")
        print("="*60)
        
        # Add 'name' column to users table (for convenience)
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
        
        # Add approval_status column
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
        
        # Add approved_by column
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
        
        # Add approval_date column
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
        
        # Add rejection_reason column
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
        
        # Add created_by column (if not exists)
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
        
        # Update existing records to have 'pending' status
        print("Updating existing records to 'pending' status...")
        cursor.execute("""
            UPDATE customer_form_data 
            SET approval_status = 'pending' 
            WHERE approval_status IS NULL
        """)
        updated_count = cursor.rowcount
        print(f"✓ Updated {updated_count} existing records to 'pending' status")
        
        # Update user names from first_name and last_name
        print("Updating user names...")
        cursor.execute("""
            UPDATE users 
            SET name = first_name || ' ' || last_name 
            WHERE name IS NULL OR name = ''
        """)
        updated_users = cursor.rowcount
        print(f"✓ Updated {updated_users} user names")
        
        # Create indexes for approval queries
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
        
        # ==========================================
        # PART 5: CREATE APPROVAL NOTIFICATIONS TABLE
        # ==========================================
        print("\n" + "="*60)
        print("PART 5: Creating Approval Notifications Table")
        print("="*60)
        
        print("Creating 'approval_notifications' table...")
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS approval_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    document_type VARCHAR(50) NOT NULL,
                    document_id INTEGER NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_read BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (document_id) REFERENCES customer_form_data(id) ON DELETE CASCADE
                )
            """)
            print("✓ Created 'approval_notifications' table")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print("⚠ 'approval_notifications' table already exists")
            else:
                raise
        
        # Create indexes for notifications
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_approval_notifications_user_id 
                ON approval_notifications(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_approval_notifications_status 
                ON approval_notifications(status)
            """)
            print("✓ Created indexes for approval_notifications")
        except sqlite3.OperationalError:
            print("⚠ Some indexes already exist")
        
        # ==========================================
        # COMMIT AND VERIFY
        # ==========================================
        print("\n" + "="*60)
        print("Committing Changes and Verifying")
        print("="*60)
        
        conn.commit()
        print("✓ All changes committed successfully!")
        
        # ==========================================
        # VERIFICATION
        # ==========================================
        print("\n" + "="*60)
        print("VERIFICATION REPORT")
        print("="*60)
        
        # Verify projects table
        print("\n1. Projects Table Schema:")
        cursor.execute("PRAGMA table_info(projects)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        
        # Check project counts
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]
        print(f"\n2. Total projects: {project_count}")
        
        if project_count > 0:
            cursor.execute("""
                SELECT project_type, COUNT(*) 
                FROM projects 
                GROUP BY project_type
            """)
            type_counts = cursor.fetchall()
            print("   Projects by type:")
            for proj_type, cnt in type_counts:
                print(f"     - {proj_type}: {cnt}")
        
        # Verify customer_form_data schema
        print("\n3. Customer Form Data Schema:")
        cursor.execute("PRAGMA table_info(customer_form_data)")
        columns = cursor.fetchall()
        important_cols = ['project_id', 'approval_status', 'approved_by', 'approval_date', 'rejection_reason', 'created_by']
        for col in columns:
            if col[1] in important_cols:
                print(f"   ✓ {col[1]} ({col[2]})")
        
        # Check form counts
        cursor.execute("SELECT COUNT(*) FROM customer_form_data")
        form_count = cursor.fetchone()[0]
        print(f"\n4. Total forms: {form_count}")
        
        if form_count > 0:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(project_id) as with_project,
                    COUNT(*) - COUNT(project_id) as without_project
                FROM customer_form_data
            """)
            counts = cursor.fetchone()
            print(f"   - Forms with project: {counts[1]}/{counts[0]}")
            print(f"   - Forms without project: {counts[2]}/{counts[0]}")
            
            cursor.execute("""
                SELECT approval_status, COUNT(*) 
                FROM customer_form_data 
                GROUP BY approval_status
            """)
            status_counts = cursor.fetchall()
            print("\n   Forms by approval status:")
            for status, cnt in status_counts:
                print(f"     - {status}: {cnt}")
        
        # Check customers
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        print(f"\n5. Total customers: {customer_count}")
        
        # Check users
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"\n6. Total users: {user_count}")
        
        print("\n" + "="*60)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nYour database now supports:")
        print("  ✓ Multiple projects per customer")
        print("  ✓ Project-linked forms")
        print("  ✓ Approval workflow for forms")
        print("  ✓ Approval notifications")
        print("\nNext steps:")
        print("  1. Update your backend code with new models")
        print("  2. Update your routes/endpoints")
        print("  3. Update your frontend to use projects")
        print("  4. Test creating new projects and forms")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()
        print("\nDatabase connection closed.")

if __name__ == "__main__":
    print("=" * 80)
    print(" " * 20 + "DATABASE MIGRATION SCRIPT")
    print(" " * 15 + "Projects & Approval Workflow")
    print("=" * 80)
    print()
    print("This script will:")
    print("  1. Create projects table")
    print("  2. Link forms to projects")
    print("  3. Migrate existing customers to default projects")
    print("  4. Add approval workflow fields")
    print("  5. Create approval notifications table")
    print()
    
    response = input("Do you want to continue? (yes/no): ").strip().lower()
    
    if response == 'yes' or response == 'y':
        print("\nStarting migration...\n")
        try:
            run_migration('database.db')
        except Exception as e:
            print("\n" + "=" * 80)
            print("❌ MIGRATION FAILED - Please check errors above")
            print("=" * 80)
            exit(1)
    else:
        print("\nMigration cancelled by user.")
        exit(0)