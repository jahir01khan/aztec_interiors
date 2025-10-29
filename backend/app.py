from flask import Flask
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
    
    # Initialize extensions
    CORS(app, 
        supports_credentials=True, 
        origins=[
            'http://localhost:3000',
            'http://localhost:3001',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:3001'
        ],
        allow_headers=['Content-Type', 'Authorization'],
        methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    )
    init_db(app)
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.approvals_routes import approvals_bp
    from routes.form_routes import form_bp
    from routes.db_routes import db_bp 
    from routes.notification_routes import notification_bp
    from routes.assignment_routes import assignment_bp
    from routes.appliance_routes import appliance_bp
    # 💡 FIX: Import the missing customer_bp
    from routes.customer_routes import customer_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(form_bp)
    app.register_blueprint(db_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(appliance_bp)
    # 💡 FIX: Register the missing customer_bp
    app.register_blueprint(customer_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")
    
    app.run(debug=True, host='127.0.0.1', port=5000)