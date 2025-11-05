from flask import Blueprint, jsonify, request, current_app
from ..models import ProductionNotification
from .auth_helpers import token_required 
from datetime import datetime
from ..db import SessionLocal # Required for database write/read operations

notification_bp = Blueprint('notification', __name__)

@notification_bp.route('/notifications/production', methods=['GET', 'OPTIONS'])
@token_required
def get_production_notifications():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    session = SessionLocal() # 👈 START SESSION FOR READ (FIXED)
    try:
        # FIXED: Replace ProductionNotification.query with session.query(ProductionNotification)
        notifications = session.query(ProductionNotification).filter_by(read=False).order_by(
            ProductionNotification.created_at.desc()
        ).all()

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
    except Exception as e:
        session.rollback()
        current_app.logger.exception(f"Error fetching production notifications: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close() # 👈 CLOSE SESSION

@notification_bp.route('/notifications/production/<string:notification_id>/read', methods=['PATCH', 'OPTIONS'])
@token_required
def mark_as_read(notification_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    # Use SessionLocal for the transaction (This was already correctly implemented)
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
    
    session = SessionLocal() # 👈 Start session
    try:
        # Update all unread notifications in one query using the session (Already correct syntax)
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