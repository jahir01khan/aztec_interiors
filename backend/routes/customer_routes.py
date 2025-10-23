from flask import Blueprint, request, jsonify
from models import Customer, db
from functools import wraps
from models import User
from flask import current_app
import uuid
from datetime import datetime
from models import CustomerFormData
import json

customer_bp = Blueprint('customers', __name__)

# Token authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        
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

@customer_bp.route('/customers', methods=['GET', 'OPTIONS'])
@token_required
def get_customers():
    """Get all customers"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customers = Customer.query.all()
        
        return jsonify([{
            'id': customer.id,
            'name': customer.name,
            'address': customer.address,
            'phone': customer.phone,
            'email': customer.email,
            'postcode': customer.postcode,
            'stage': customer.stage,
            'salesperson': customer.salesperson,
            'project_types': customer.project_types,
        } for customer in customers]), 200
        
    except Exception as e:
        print(f"Error fetching customers: {e}")
        return jsonify({'error': 'Failed to fetch customers'}), 500

@customer_bp.route('/customers', methods=['POST', 'OPTIONS'])
@token_required
def create_customer():
    """Create a new customer"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Name is required'}), 400
        if not data.get('phone'):
            return jsonify({'error': 'Phone is required'}), 400
        if not data.get('address'):
            return jsonify({'error': 'Address is required'}), 400
        
        # Create new customer
        new_customer = Customer(
            id=str(uuid.uuid4()),
            name=data.get('name'),
            phone=data.get('phone'),
            email=data.get('email', ''),
            address=data.get('address'),
            postcode=data.get('postcode', ''),
            salesperson=data.get('salesperson', ''),
            project_types=data.get('project_types', []),
            marketing_opt_in=data.get('marketing_opt_in', False),
            notes=data.get('notes', ''),
            status='New Lead',
            stage='Lead',
            contact_made='No',
            preferred_contact_method='Phone',
            created_at=datetime.utcnow(),
            created_by=request.current_user.id
        )
        
        db.session.add(new_customer)
        db.session.commit()
        
        current_app.logger.info(f"Customer {new_customer.id} created by user {request.current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Customer created successfully',
            'customer': {
                'id': new_customer.id,
                'name': new_customer.name,
                'phone': new_customer.phone,
                'email': new_customer.email,
                'address': new_customer.address,
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error creating customer: {e}")
        return jsonify({'error': f'Failed to create customer: {str(e)}'}), 500
    


@customer_bp.route('/customers/<string:customer_id>', methods=['GET', 'OPTIONS'])
@token_required
def get_customer(customer_id):
    """Get a single customer by ID"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Check access permissions
        if request.current_user.role == 'Sales':
            # Sales can only view customers they created or are assigned to
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.name:
                return jsonify({'error': 'You do not have permission to view this customer'}), 403
        elif request.current_user.role == 'Staff':
            # Staff can only view customers they created or are assigned to
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.name:
                return jsonify({'error': 'You do not have permission to view this customer'}), 403
        
        # Fetch form submissions
        form_entries = CustomerFormData.query.filter_by(customer_id=customer.id).order_by(CustomerFormData.submitted_at.desc()).all()
        
        form_submissions = []
        for f in form_entries:
            try:
                parsed = json.loads(f.form_data)
            except Exception:
                parsed = {"raw": f.form_data}
            
            form_submissions.append({
                "id": f.id,
                "token_used": f.token_used,
                "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
                "form_data": parsed,
                "source": "web_form"
            })
        
        return jsonify({
            'id': customer.id,
            'name': customer.name,
            'address': customer.address,
            'postcode': customer.postcode,
            'phone': customer.phone,
            'email': customer.email,
            'contact_made': customer.contact_made,
            'preferred_contact_method': customer.preferred_contact_method,
            'marketing_opt_in': customer.marketing_opt_in,
            'date_of_measure': customer.date_of_measure.isoformat() if customer.date_of_measure else None,
            'status': customer.status,
            'stage': customer.stage,
            'notes': customer.notes,
            'created_at': customer.created_at.isoformat() if customer.created_at else None,
            'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
            'created_by': customer.created_by,
            'updated_by': customer.updated_by,
            'salesperson': customer.salesperson,
            'project_types': customer.project_types or [],
            'form_submissions': form_submissions
        }), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching customer {customer_id}: {e}")
        return jsonify({'error': 'Failed to fetch customer'}), 500