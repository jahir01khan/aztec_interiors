# /Users/razataiab/Desktop/aztec_interiors/backend/routes/notification_routes.py

from flask import Blueprint, jsonify, request
from database import db
from models import ProductionNotification
from .auth_helpers import token_required # Import the shared decorator
from datetime import datetime

notification_bp = Blueprint('notification', __name__)

@notification_bp.route('/notifications/production', methods=['GET', 'OPTIONS'])
@token_required # <-- THIS IS THE FIX
def get_production_notifications():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    # Ensure only Production roles can access this
    if request.current_user.role != "Production":
        return jsonify({'error': 'Not authorized'}), 403

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
@token_required # <-- THIS IS THE FIX
def mark_as_read(notification_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    if request.current_user.role != "Production":
        return jsonify({'error': 'Not authorized'}), 403

    notification = ProductionNotification.query.get(notification_id)
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
        
    try:
        notification.read = True
        db.session.commit()
        return jsonify({'message': 'Notification marked as read'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@notification_bp.route('/notifications/production/mark-all-read', methods=['PATCH', 'OPTIONS'])
@token_required # <-- THIS IS THE FIX
def mark_all_as_read():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    if request.current_user.role != "Production":
        return jsonify({'error': 'Not authorized'}), 403

    try:
        # Update all unread notifications in one query
        ProductionNotification.query.filter_by(read=False).update({'read': True})
        db.session.commit()
        return jsonify({'message': 'All notifications marked as read'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500