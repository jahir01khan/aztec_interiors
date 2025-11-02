from flask import Flask, request, jsonify, g
from flask_cors import CORS
from database import db, init_db
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
    # CORS CONFIGURATION - ALLOW ALL
    # ============================================
    CORS(app, 
         resources={r"/*": {
             "origins": "*",
             "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
             "expose_headers": ["Content-Type", "Authorization"],
             "supports_credentials": False,
             "max_age": 3600
         }})
    
    # Add CORS headers to every response
    @app.after_request
    def after_request(response):
        origin = request.headers.get('Origin')
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    # ============================================
    # OPTIONS HANDLER - HANDLE ALL PREFLIGHT
    # ============================================
    @app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
    @app.route('/<path:path>', methods=['OPTIONS'])
    def handle_options(path=''):
        """Handle all OPTIONS requests (CORS preflight)"""
        return '', 200
    
    # ============================================
    # MOCK AUTH MIDDLEWARE - ACCEPT MOCK TOKEN
    # ============================================
    @app.before_request
    def check_auth():
        """Accept mock token temporarily for frontend development"""
        # Skip auth check for OPTIONS requests
        if request.method == 'OPTIONS':
            return None
        
        # Skip auth for public endpoints
        if request.path.startswith('/submit-customer-form') or request.path.startswith('/form'):
            return None
            
        # Get auth header
        auth_header = request.headers.get('Authorization', '')
        
        if auth_header:
            token = auth_header.replace('Bearer ', '')
            
            # ✅ ACCEPT MOCK TOKEN
            if token == 'mock-jwt-token-123':
                print(f"✅ Mock token accepted for {request.method} {request.path}")
                g.user = {
                    'id': 1,
                    'email': 'test@example.com',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'role': 'manager'
                }
                return None
        
        # ✅ ALLOW REQUESTS WITHOUT AUTH (for testing)
        print(f"⚠️ No auth for {request.method} {request.path} - allowing anyway")
        g.user = {
            'id': 1,
            'email': 'test@example.com',
            'role': 'manager'
        }
        return None
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.approvals_routes import approvals_bp
    from routes.form_routes import form_bp
    from routes.db_routes import db_bp 
    from routes.notification_routes import notification_bp
    from routes.assignment_routes import assignment_bp
    from routes.appliance_routes import appliance_bp
    from routes.customer_routes import customer_bp
    from routes.file_routes import file_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(form_bp)
    app.register_blueprint(db_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(appliance_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(file_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    with app.app_context():
        db.create_all()
        print("=" * 50)
        print("✅ Database tables created successfully!")
        print("✅ CORS enabled for all origins")
        print("✅ Mock token 'mock-jwt-token-123' will be accepted")
        print("✅ Server starting...")
        print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)