from flask import Blueprint, request, jsonify
from ..models import Customer, Project, CustomerFormData, db, User, Job, DrawingDocument
from functools import wraps
from flask import current_app
import uuid
from datetime import datetime
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


# ==========================================
# CUSTOMER ENDPOINTS
# ==========================================

@customer_bp.route('/customers', methods=['GET', 'OPTIONS'])
@token_required
def get_customers():
    """Get all customers with their project counts"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customers = Customer.query.all()
        
        return jsonify([customer.to_dict(include_projects=False) for customer in customers]), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching customers: {e}")
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
            marketing_opt_in=data.get('marketing_opt_in', False),
            notes=data.get('notes', ''),
            contact_made='No',
            preferred_contact_method='Phone',
            created_at=datetime.utcnow(),
            created_by=request.current_user.id
        )
        
        session = SessionLocal()
# ...do stuff...
        session.add(new_customer)
        session.commit()
        session.close()

        session = SessionLocal()
# ...do stuff...
        session.add(new_customer)
        session.commit()
        session.close()
        session.commit()
        
        current_app.logger.info(f"Customer {new_customer.id} created by user {request.current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Customer created successfully',
            'customer': new_customer.to_dict()
        }), 201
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error creating customer: {e}")
        return jsonify({'error': f'Failed to create customer: {str(e)}'}), 500


@customer_bp.route('/customers/<string:customer_id>', methods=['GET', 'OPTIONS'])
@token_required
def get_customer(customer_id):
    """Get a single customer by ID with all their projects"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Check access permissions
        if request.current_user.role == 'Sales':
            # Sales can only view customers they created or are assigned to
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to view this customer'}), 403
        elif request.current_user.role == 'Staff':
            # Staff can only view customers they created or are assigned to
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to view this customer'}), 403
        
        # Return customer with all projects
        return jsonify(customer.to_dict(include_projects=True)), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching customer {customer_id}: {e}")
        return jsonify({'error': 'Failed to fetch customer'}), 500


@customer_bp.route('/customers/<string:customer_id>', methods=['PUT', 'OPTIONS'])
@token_required
def update_customer(customer_id):
    """Update a customer"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Check permissions
        if request.current_user.role == 'Sales':
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to edit this customer'}), 403
        
        data = request.get_json()
        
        # Update customer fields
        if 'name' in data:
            customer.name = data['name']
        if 'phone' in data:
            customer.phone = data['phone']
        if 'email' in data:
            customer.email = data['email']
        if 'address' in data:
            customer.address = data['address']
        if 'postcode' in data:
            customer.postcode = data['postcode']
        if 'contact_made' in data:
            customer.contact_made = data['contact_made']
        if 'preferred_contact_method' in data:
            customer.preferred_contact_method = data['preferred_contact_method']
        if 'marketing_opt_in' in data:
            customer.marketing_opt_in = data['marketing_opt_in']
        if 'notes' in data:
            customer.notes = data['notes']
        if 'salesperson' in data:
            customer.salesperson = data['salesperson']
        
        customer.updated_by = request.current_user.id
        customer.updated_at = datetime.utcnow()
        
        session = SessionLocal()
# ...do stuff...
        session.add(customer)
        session.commit()
        session.close()
        session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer updated successfully',
            'customer': customer.to_dict(include_projects=True)
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error updating customer {customer_id}: {e}")
        return jsonify({'error': f'Failed to update customer: {str(e)}'}), 500


@customer_bp.route('/customers/<string:customer_id>', methods=['DELETE', 'OPTIONS'])
@token_required
def delete_customer(customer_id):
    """Delete a customer (Manager/HR only)"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        # Only Manager and HR can delete
        if request.current_user.role not in ['Manager', 'HR']:
            return jsonify({'error': 'You do not have permission to delete customers'}), 403
        
        customer = Customer.query.get_or_404(customer_id)
        
        # Check if customer has projects - warn if they do
        if customer.projects:
            return jsonify({
                'error': f'Cannot delete customer with {len(customer.projects)} project(s). Delete projects first.'
            }), 400
        
        session = SessionLocal()
# ...do stuff...
        session.add(customer)
        session.commit()
        session.close()
        session.delete(customer)
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.commit()
        
        current_app.logger.info(f"Customer {customer_id} deleted by user {request.current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Customer deleted successfully'
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error deleting customer {customer_id}: {e}")
        return jsonify({'error': 'Failed to delete customer'}), 500


# ==========================================
# PROJECT ENDPOINTS
# ==========================================

@customer_bp.route('/customers/<string:customer_id>/projects', methods=['GET', 'OPTIONS'])
@token_required
def get_customer_projects(customer_id):
    """Get all projects for a specific customer"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Check permissions
        if request.current_user.role in ['Sales', 'Staff']:
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to view projects for this customer'}), 403
        
        projects = Project.query.filter_by(customer_id=customer_id).order_by(Project.created_at.desc()).all()
        
        return jsonify([project.to_dict(include_forms=False) for project in projects]), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching projects for customer {customer_id}: {e}")
        return jsonify({'error': 'Failed to fetch projects'}), 500


@customer_bp.route('/customers/<string:customer_id>/projects', methods=['POST', 'OPTIONS'])
@token_required
def create_project(customer_id):
    """
    Create a new project for a customer.
    
    🔥 FIXED: Stop conditional stage sync on creation as it causes overwrites.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        # Check permissions
        if request.current_user.role in ['Sales', 'Staff']:
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to create projects for this customer'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('project_name'):
            return jsonify({'error': 'Project name is required'}), 400
        if not data.get('project_type'):
            return jsonify({'error': 'Project type is required'}), 400
        
        # Create new project
        new_project = Project(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            project_name=data.get('project_name'),
            project_type=data.get('project_type'),
            stage=data.get('stage', 'Lead'),
            date_of_measure=datetime.fromisoformat(data['date_of_measure']) if data.get('date_of_measure') else None,
            notes=data.get('notes', ''),
            created_at=datetime.utcnow(),
            created_by=request.current_user.id
        )
        
        session = SessionLocal()
# ...do stuff...
        session.add(new_project)
        session.commit()
        session.close()
        
        # --- CRITICAL FIX 1: SIMPLIFY STAGE SYNC ON CREATION ---
        
        # Count existing linked entities. We must commit the new project first to get a true count of ALL linked entities.
        # However, to avoid a race condition, we check the database for pre-existing entities (committed ones).
        existing_project_count = Project.query.filter_by(customer_id=customer_id).count()
        existing_job_count = Job.query.filter_by(customer_id=customer_id).count()
                                   
        # If the combined count is ZERO, this new project is the FIRST entity, so sync the customer's overall stage.
        if existing_project_count == 0 and existing_job_count == 0 and new_project.stage:
            customer.stage = new_project.stage
            
        # --- END CRITICAL FIX 1 ---
        
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.commit()
        
        current_app.logger.info(f"Project {new_project.id} created for customer {customer_id} by user {request.current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Project created successfully',
            'project': new_project.to_dict()
        }), 201
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error creating project for customer {customer_id}: {e}")
        return jsonify({'error': f'Failed to create project: {str(e)}'}), 500


@customer_bp.route('/projects/<string:project_id>', methods=['GET', 'OPTIONS'])
@token_required
def get_project(project_id):
    """Get a specific project with all its details"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        project = Project.query.get_or_404(project_id)
        customer = project.customer
        
        # Check permissions
        if request.current_user.role in ['Sales', 'Staff']:
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to view this project'}), 403
        
        return jsonify(project.to_dict(include_forms=True)), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching project {project_id}: {e}")
        return jsonify({'error': 'Failed to fetch project'}), 500


@customer_bp.route('/projects/<string:project_id>', methods=['PUT', 'OPTIONS'])
@token_required
def update_project(project_id):
    """
    Update a project (Used by frontend drag-and-drop/edit).
    
    🔥 CRITICAL FIX 2: Stop conditional stage update on PUT to prevent multi-project stage issues.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        project = Project.query.get_or_404(project_id)
        customer = project.customer
        
        # Check permissions
        if request.current_user.role in ['Sales', 'Staff']:
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to edit this project'}), 403
        
        data = request.get_json()
        
        old_stage = project.stage # Capture old stage for comparison/sync logic
        
        # Update fields
        if 'project_name' in data:
            project.project_name = data['project_name']
        if 'project_type' in data:
            project.project_type = data['project_type']
        if 'stage' in data:
            project.stage = data['stage'] # Update the Project's specific stage
        if 'date_of_measure' in data:
            project.date_of_measure = datetime.fromisoformat(data['date_of_measure']) if data['date_of_measure'] else None
        if 'notes' in data:
            project.notes = data['notes']
        
        project.updated_by = request.current_user.id
        project.updated_at = datetime.utcnow()
        
        # --- CRITICAL FIX 2: CONDITIONAL CUSTOMER STAGE SYNC RE-EVALUATED ---
        
        # Count existing linked entities (Projects + Jobs)
        # We must exclude the current project being updated from the count 
        # to correctly check if it is the ONLY remaining entity.
        total_other_linked_entities = Project.query.filter(Project.customer_id==customer.id, Project.id != project_id).count() + \
                                      Job.query.filter_by(customer_id=customer.id).count()
        
        # If the stage changed AND there are NO other entities, sync the customer's overall stage.
        if 'stage' in data and project.stage != old_stage and total_other_linked_entities == 0:
            customer.stage = project.stage
            
        # --- END CRITICAL FIX 2 ---
        
        session = SessionLocal()
# ...do stuff...
        session.add(project)
        session.commit()
        session.close()
        session.commit()
        
        current_app.logger.info(f"Project {project_id} updated by user {request.current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Project updated successfully',
            'project': project.to_dict(include_forms=True)
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error updating project {project_id}: {e}")
        return jsonify({'error': f'Failed to update project: {str(e)}'}), 500


@customer_bp.route('/projects/<string:project_id>', methods=['DELETE', 'OPTIONS'])
@token_required
def delete_project(project_id):
    """Delete a project (Manager/HR only)"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        # Only Manager and HR can delete
        if request.current_user.role not in ['Manager', 'HR']:
            return jsonify({'error': 'You do not have permission to delete projects'}), 403
        
        project = Project.query.get_or_404(project_id)
        
        session = SessionLocal()
# ...do stuff...
        session.add(project)
        session.commit()
        session.close()
        session.delete(project)
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.commit()
        
        current_app.logger.info(f"Project {project_id} deleted by user {request.current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Project deleted successfully'
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error deleting project {project_id}: {e}")
        return jsonify({'error': 'Failed to delete project'}), 500


# ==========================================
# PROJECT FORMS ENDPOINTS
# ==========================================

@customer_bp.route('/projects/<string:project_id>/forms', methods=['GET', 'OPTIONS'])
@token_required
def get_project_forms(project_id):
    """Get all forms for a specific project"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        project = Project.query.get_or_404(project_id)
        customer = project.customer
        
        # Check permissions
        if request.current_user.role in ['Sales', 'Staff']:
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to view forms for this project'}), 403
        
        forms = CustomerFormData.query.filter_by(project_id=project_id).order_by(CustomerFormData.submitted_at.desc()).all()
        
        return jsonify([form.to_dict() for form in forms]), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching forms for project {project_id}: {e}")
        return jsonify({'error': 'Failed to fetch forms'}), 500
    
# ==========================================
# DRAWING DOCUMENTS ENDPOINTS (NEW)
# ==========================================

@customer_bp.route('/drawings', methods=['GET', 'OPTIONS'])
@token_required
def get_drawing_documents():
    """Get all drawing documents for a specific customer"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        customer_id = request.args.get('customer_id')
        if not customer_id:
            return jsonify({'error': 'Customer ID is required'}), 400
        
        customer = Customer.query.get_or_404(customer_id)
        
        # Check permissions (same as customer/project access)
        if request.current_user.role in ['Sales', 'Staff']:
            if customer.created_by != request.current_user.id and customer.salesperson != request.current_user.get_full_name():
                return jsonify({'error': 'You do not have permission to view documents for this customer'}), 403
        
        # Fetch all drawing documents for the customer
        drawings = DrawingDocument.query.filter_by(customer_id=customer_id).order_by(DrawingDocument.created_at.desc()).all()
        
        return jsonify([drawing.to_dict() for drawing in drawings]), 200
        
    except Exception as e:
        current_app.logger.exception(f"Error fetching drawing documents: {e}")
        return jsonify({'error': 'Failed to fetch drawing documents'}), 500

@customer_bp.route('/drawings/<string:drawing_id>', methods=['DELETE', 'OPTIONS'])
@token_required
def delete_drawing_document(drawing_id):
    """Delete a drawing document (Manager/HR/Creator only - simplified to Manager/HR for now)"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        # Permission check
        if request.current_user.role not in ['Manager', 'HR']:
            return jsonify({'error': 'You do not have permission to delete documents'}), 403
        
        drawing = DrawingDocument.query.get_or_404(drawing_id)
        
        # NOTE: In a real app, you must **delete the actual file** from S3/disk here
        
        session = SessionLocal()
# ...do stuff...
        session.add(drawing)
        session.commit()
        session.close()
        session.delete(drawing)
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.commit()
        
        current_app.logger.info(f"Drawing document {drawing_id} deleted by user {request.current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Drawing document deleted successfully'
        }), 200
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error deleting drawing document {drawing_id}: {e}")
        return jsonify({'error': 'Failed to delete drawing document'}), 500


# ==========================================
# FORM SUBMISSION ENDPOINT (Updated)
# ==========================================

@customer_bp.route('/forms/submit', methods=['POST', 'OPTIONS'])
def submit_form():
    """Submit a form linked to a project (public endpoint - no auth required)"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.get_json()
        token = data.get('token')
        customer_id = data.get('customer_id')
        project_id = data.get('project_id')  # REQUIRED: project_id must be provided
        
        if not token:
            return jsonify({'error': 'Token is required'}), 400
        if not customer_id:
            return jsonify({'error': 'Customer ID is required'}), 400
        if not project_id:
            return jsonify({'error': 'Project ID is required'}), 400
        
        # Validate customer exists
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Validate project exists and belongs to customer
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        if project.customer_id != customer_id:
            return jsonify({'error': 'Project does not belong to this customer'}), 400
        
        # Create form submission
        form_submission = CustomerFormData(
            customer_id=customer_id,
            project_id=project_id,
            token_used=token,
            form_data=json.dumps(data.get('form_data', {})),
            submitted_at=datetime.utcnow()
        )
        
        session = SessionLocal()
# ...do stuff...
        session.add(form_submission)
        session.commit()
        session.close()

        session = SessionLocal()
# ...do stuff...
        session.add(form_submission)
        session.commit()
        session.close()
        session.commit()
        
        current_app.logger.info(f"Form submitted for project {project_id}")
        
        return jsonify({
            'success': True,
            'message': 'Form submitted successfully',
            'form_id': form_submission.id
        }), 201
        
    except Exception as e:
        session = SessionLocal()
# ...do stuff...
        session.add(None)
        session.commit()
        session.close()
        session.rollback()
        current_app.logger.exception(f"Error submitting form: {e}")
        return jsonify({'error': f'Failed to submit form: {str(e)}'}), 500