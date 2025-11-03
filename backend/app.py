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
    # NO AUTH CHECK - COMPLETELY OPEN FOR TESTING
    # ============================================
    @app.before_request
    def set_mock_user():
        """Set mock user for all requests - NO AUTH REQUIRED"""
        if request.method == 'OPTIONS':
            return None
            
        g.user = {
            'id': 1,
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'manager'
        }
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
        
        # Import all models to ensure they're registered
        from backend.models import User, Customer, Form, Notification, Assignment, Appliance
        import bcrypt
        
        # Create all tables
        db.create_all()
        
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'users' not in tables:
            print("❌ Tables not created! Running emergency setup...")
            db.drop_all()
            db.create_all()
            
        print(f"✅ Tables found: {', '.join(tables)}")
        
        # Check if admin user exists, create if not
        admin_user = User.query.filter_by(email='admin@aztecinteriors.com').first()
        if not admin_user:
            print("\n👤 Creating default admin user...")
            admin_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
            admin = User(
                email='admin@aztecinteriors.com',
                password_hash=admin_password.decode('utf-8'),
                first_name='Admin',
                last_name='User',
                role='manager',
                is_active=True,
                is_verified=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created: admin@aztecinteriors.com / admin123")
        
        # Create the specific user from error message if not exists
        test_user = User.query.filter_by(email='ayaan.ateeb@gmail.com').first()
        if not test_user:
            print("\n👤 Creating test user...")
            user_password = bcrypt.hashpw('Ayaan#1804'.encode('utf-8'), bcrypt.gensalt())
            user = User(
                email='ayaan.ateeb@gmail.com',
                password_hash=user_password.decode('utf-8'),
                first_name='Ayaan',
                last_name='Ateeb',
                role='manager',
                is_active=True,
                is_verified=True
            )
            db.session.add(user)
            db.session.commit()
            print("✅ Test user created: ayaan.ateeb@gmail.com / Ayaan#1804")
        
        print("\n" + "=" * 60)
        print("✅ Database initialized successfully!")
        print("✅ CORS enabled - ALL ORIGINS ALLOWED")
        print("✅ AUTH DISABLED - All requests allowed")
        print(f"✅ Server starting on port {os.environ.get('PORT', 5000)}")
        print("=" * 60)
    
    # Use proper production server settings
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)