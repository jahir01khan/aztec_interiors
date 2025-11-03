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
        print(f"✅ {request.method} {request.path} - Mock user set")
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
        db.create_all()
        print("=" * 50)
        print("✅ Database tables created successfully!")
        print("✅ CORS enabled - ALL ORIGINS ALLOWED")
        print("✅ AUTH DISABLED - All requests allowed")
        print("✅ Server starting on port", os.environ.get('PORT', 5000))
        print("=" * 50)
    
    # Use proper production server settings
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)