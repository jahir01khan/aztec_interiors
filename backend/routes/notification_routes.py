from flask import Blueprint, jsonify, request
# REMOVED: from ..database import db 
from ..models import ProductionNotification
from .auth_helpers import token_required 
from datetime import datetime
# 👈 NEW IMPORT: Required for database write operations
from ..db import SessionLocal 


notification_bp = Blueprint('notification', __name__)

@notification_bp.route('/notifications/production', methods=['GET', 'OPTIONS'])
@token_required
def get_production_notifications():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    # Role check removed as requested (Task 2)

    # Note: ProductionNotification.query is used, assuming implicit session handling for reads.
    notifications = ProductionNotification.query.filter_by(read=False).order_by(ProductionNotification.created_at.desc()).all()

    return jsonify([
        {
            'id': n.id,
            'job_id': n.job_id,
            'customer_id': n.customer_id,
            'message': n.message,
            'created_at': n.created_at.isoformat(),
            'moved_by': n.moved_by
        } for n in notifications
    ])

@notification_bp.route('/notifications/production/<string:notification_id>/read', methods=['PATCH', 'OPTIONS'])
@token_required
def mark_as_read(notification_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    # Role check removed as requested (Task 2)
    
    # Use SessionLocal for the transaction
    session = SessionLocal() 
    try:
        # Fetch the notification within the current transaction session
        notification = session.get(ProductionNotification, notification_id)
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404

        notification.read = True
        
        session.commit() # 👈 Commit transaction
        
        return jsonify({'message': 'Notification marked as read'}), 200
    except Exception as e:
        session.rollback() # 👈 Rollback on error
        current_app.logger.exception(f"Error marking notification {notification_id} as read: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close() # 👈 Close session

@notification_bp.route('/notifications/production/mark-all-read', methods=['PATCH', 'OPTIONS'])
@token_required
def mark_all_as_read():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    # Role check removed as requested (Task 2)
    
    session = SessionLocal() # 👈 Start session
    try:
        # Update all unread notifications in one query using the session
        session.query(ProductionNotification).filter_by(read=False).update(
            {'read': True},
            synchronize_session='fetch'
        )
        
        session.commit() # 👈 Commit transaction
            
        return jsonify({'message': 'All notifications marked as read'}), 200
    except Exception as e:
        session.rollback() # 👈 Rollback on error
        current_app.logger.exception(f"Error marking all notifications as read: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close() # 👈 Close session