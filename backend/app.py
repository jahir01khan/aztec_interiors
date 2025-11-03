from flask import Flask, request, jsonify, g
from flask_cors import CORS
from backend.database import db, init_db
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # SQLite Configuration
    db_path = os.getenv('DATABASE_PATH', 'database.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # ============================================
    # CORS CONFIGURATION - MAXIMUM PERMISSIVE
    # ============================================
    CORS(app, 
         resources={r"/*": {
             "origins": "*",
             "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
             "allow_headers": "*",
             "expose_headers": "*",
             "supports_credentials": False,
             "max_age": 3600
         }})
    
    # ============================================
    # HANDLE PREFLIGHT FIRST - BEFORE ANYTHING
    # ============================================
    @app.before_request
    def handle_preflight():
        if request.method == 'OPTIONS':
            response = jsonify({'status': 'ok'})
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            response.headers['Access-Control-Max-Age'] = '3600'
            return response, 200
    
    # Add CORS headers to every response
    @app.after_request
    def after_request(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    # ============================================
    # MOCK AUTH - NO AUTHENTICATION REQUIRED
    # ============================================
    @app.before_request
    def set_mock_user():
        """Set mock user for all requests - NO AUTH REQUIRED"""
        if request.method == 'OPTIONS':
            return None
            
        # Try to get first real user from database, otherwise use mock
        from backend.models import User
        try:
            first_user = User.query.first()
            if first_user:
                g.user = first_user
            else:
                g.user = type('User', (), {
                    'id': 1,
                    'email': 'dev@test.com',
                    'first_name': 'Dev',
                    'last_name': 'User',
                    'role': 'Manager',
                    'is_active': True
                })()
        except:
            g.user = type('User', (), {
                'id': 1,
                'email': 'dev@test.com',
                'first_name': 'Dev',
                'last_name': 'User',
                'role': 'Manager',
                'is_active': True
            })()
        return None
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    from backend.routes.auth_routes import auth_bp
    from backend.routes.approvals_routes import approvals_bp
    from backend.routes.form_routes import form_bp
    from backend.routes.db_routes import db_bp 
    from backend.routes.notification_routes import notification_bp
    from backend.routes.assignment_routes import assignment_bp
    from backend.routes.appliance_routes import appliance_bp
    from backend.routes.customer_routes import customer_bp
    from backend.routes.file_routes import file_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(form_bp)
    app.register_blueprint(db_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(appliance_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(file_bp)
    
    # ============================================
    # HEALTH CHECK ENDPOINT
    # ============================================
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'ok', 'message': 'Server is running'}), 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("🔧 INITIALIZING DATABASE...")
        print("=" * 60)
        
        # Import ALL models to ensure they're registered with SQLAlchemy
        from backend.models import (
            User, LoginAttempt, Session, Customer, Project, Team, Fitter, 
            Salesperson, Job, JobDocument, JobChecklist, ChecklistItem,
            ScheduleItem, Room, RoomAppliance, JobFormLink, JobNote,
            ApplianceCategory, Brand, Product, Quotation, QuotationItem,
            ProductQuoteItem, Invoice, InvoiceLineItem, Payment, CountingSheet,
            CountingItem, RemedialAction, RemedialItem, DocumentTemplate,
            AuditLog, VersionedSnapshot, ProductionNotification, FormSubmission,
            CustomerFormData, ApprovalNotification, DataImport, DrawingDocument,
            Assignment
        )
        
        print("✅ All models imported")
        
        # Force create all tables
        db.create_all()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"   ✓ {table}")
        
        # Check if users table exists and has data
        if 'users' in tables:
            user_count = User.query.count()
            print(f"\n👤 Users in database: {user_count}")
            
            if user_count == 0:
                print("\n⚠️  No users found! Run 'python backend/init_db.py' to create default users")
            else:
                users = User.query.all()
                print("\n✅ Existing users:")
                for u in users:
                    print(f"   📧 {u.email} ({u.role})")
        else:
            print("\n❌ ERROR: users table was not created!")
            print("   Please check your models.py file")
        
        print("\n" + "=" * 60)
        print("✅ Database check complete!")
        print("=" * 60)
    
    # Use proper production server settings
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)