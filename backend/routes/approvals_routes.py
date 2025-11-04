from functools import wraps # Moved to the top

from flask import Blueprint, request, jsonify
from datetime import datetime
from ..models import CustomerFormData, User, Customer, ApprovalNotification
from flask import current_app
import json

approvals_bp = Blueprint('approvals', __name__)

# Token authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Allow OPTIONS requests without authentication (for CORS)
        if request.method == 'OPTIONS':
            return jsonify({}), 200  # Add this line
        
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            current_user = User.verify_jwt_token(token, current_app.config['SECRET_KEY'])
            if not current_user:
                return jsonify({'error': 'Token is invalid or expired'}), 401
            
            request.current_user = current_user
            
        except Exception as e:
            return jsonify({'error': 'Token verification failed'}), 401
        
        return f(*args, **kwargs)
    
    return decorated

# Manager-only decorator
def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({'error': 'Authentication required'}), 401
        
        if request.current_user.role not in ['Manager', 'HR']:
            return jsonify({'error': 'Manager or HR access required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

# Get all pending approvals (for managers)
@approvals_bp.route('/approvals/pending', methods=['GET', 'OPTIONS'])
@token_required
@manager_required
def get_pending_approvals():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        pending_submissions = CustomerFormData.query.filter_by(
            approval_status='pending'
        ).order_by(CustomerFormData.submitted_at.desc()).all()
        
        all_pending = []
        
        for submission in pending_submissions:
            form_data = json.loads(submission.form_data)
            creator = User.query.get(submission.created_by) if submission.created_by else None
            customer = Customer.query.get(submission.customer_id)
            
            doc_type = 'form'
            if form_data.get('is_invoice'):
                doc_type = 'invoice'
            elif form_data.get('is_receipt'):
                doc_type = 'receipt'
            elif form_data.get('form_type') in ['kitchen', 'bedroom']:
                doc_type = 'checklist'
            
            pending_item = {
                'id': submission.id,
                'type': doc_type,
                'invoice_number': form_data.get('invoiceNumber'),
                'receipt_number': form_data.get('receiptType'),
                'customer_name': customer.name if customer else form_data.get('customerName', 'N/A'),
                'total_amount': form_data.get('totalAmount') or form_data.get('paidAmount'),
                'created_by': creator.get_full_name() if creator else 'Unknown',
                'created_at': submission.submitted_at.isoformat()
            }
            all_pending.append(pending_item)
        
        return jsonify({'success': True, 'data': all_pending}), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching pending approvals: {e}")
        return jsonify({'error': 'Failed to fetch pending approvals'}), 500

# Approve a document
@approvals_bp.route('/approvals/approve', methods=['POST', 'OPTIONS'])
@token_required
@manager_required
def approve_document():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        document_id = data.get('documentId')
        
        if not document_id:
            return jsonify({'error': 'Missing document ID'}), 400
        
        submission = CustomerFormData.query.get(document_id)
        if not submission:
            return jsonify({'error': 'Document not found'}), 404
        
        submission.approval_status = 'approved'
        submission.approved_by = request.current_user.id
        submission.approval_date = datetime.utcnow()
        
        form_data = json.loads(submission.form_data)
        doc_type = 'document'
        if form_data.get('is_invoice'):
            doc_type = 'invoice'
        elif form_data.get('is_receipt'):
            doc_type = 'receipt'
        
        current_app.logger.info(
            f"Document {document_id} ({doc_type}) approved by manager {request.current_user.id}"
        )
        
        session = SessionLocal()
# ...do stuff...
        session.add(submission)
        session.commit()
        session.close()
        session.commit()
        
        return jsonify({'success': True, 'message': 'Document approved successfully'}), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error approving document: {e}")
        return jsonify({'error': 'Failed to approve document'}), 500

# Reject a document
@approvals_bp.route('/approvals/reject', methods=['POST', 'OPTIONS'])
@token_required
@manager_required
def reject_document():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        document_id = data.get('documentId')
        reason = data.get('reason', '')
        
        if not document_id:
            return jsonify({'error': 'Missing document ID'}), 400
        
        if not reason.strip():
            return jsonify({'error': 'Rejection reason is required'}), 400
        
        submission = CustomerFormData.query.get(document_id)
        if not submission:
            return jsonify({'error': 'Document not found'}), 404
        
        submission.approval_status = 'rejected'
        submission.approved_by = request.current_user.id
        submission.approval_date = datetime.utcnow()
        submission.rejection_reason = reason
        
        form_data = json.loads(submission.form_data)
        doc_type = 'document'
        if form_data.get('is_invoice'):
            doc_type = 'invoice'
        elif form_data.get('is_receipt'):
            doc_type = 'receipt'
        
        current_app.logger.info(
            f"Document {document_id} ({doc_type}) rejected by manager {request.current_user.id}. Reason: {reason}"
        )
        
        session = SessionLocal()
# ...do stuff...
        session.add(submission)
        session.commit()
        session.close()
        session.commit()
        
        return jsonify({'success': True, 'message': 'Document rejected'}), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error rejecting document: {e}")
        return jsonify({'error': 'Failed to reject document'}), 500