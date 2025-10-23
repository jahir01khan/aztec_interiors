
from flask import Blueprint, request, jsonify, send_file
import json
from functools import wraps
from database import db
from models import User, Assignment, Customer, CustomerFormData, Fitter, Job, ProductionNotification, Quotation, QuotationItem
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# Create blueprint
from .auth_helpers import token_required
db_bp = Blueprint('database', __name__)


@db_bp.route('/customers', methods=['GET', 'POST'])
@token_required
def handle_customers():
    if request.method == 'OPTIONS': # Handle OPTIONS
        return jsonify({}), 200
    
    if request.method == 'POST':
        data = request.json
        
        # Create new customer - ensure stage defaults to Lead
        customer = Customer(
            name=data.get('name', ''),
            date_of_measure=datetime.strptime(data['date_of_measure'], '%Y-%m-%d').date() if data.get('date_of_measure') else None,
            address=data.get('address', ''),
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            contact_made=data.get('contact_made', 'Unknown'),
            preferred_contact_method=data.get('preferred_contact_method'),
            marketing_opt_in=data.get('marketing_opt_in', False),
            notes=data.get('notes', ''),
            stage=data.get('stage', 'Lead'),  # ENSURE DEFAULT IS Lead
            created_by=request.current_user.email if hasattr(request, 'current_user') else data.get('created_by', 'System'),
            status=data.get('status', 'Active'),
            project_types=data.get('project_types', []),
            salesperson=data.get('salesperson'),
        )
        
        customer.save()
        
        return jsonify({
            'id': customer.id,
            'message': 'Customer created successfully'
        }), 201
    
    # GET all customers
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return jsonify([
        {
            'id': c.id,
            'name': c.name,
            'address': c.address,
            'postcode': c.postcode,
            'phone': c.phone,
            'email': c.email,
            'contact_made': c.contact_made,
            'preferred_contact_method': c.preferred_contact_method,
            'marketing_opt_in': c.marketing_opt_in,
            'date_of_measure': c.date_of_measure.isoformat() if c.date_of_measure else None,
            'status': c.status,
            'stage': c.stage,
            'notes': c.notes,
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'created_by': c.created_by,
            'project_types': c.project_types or [],
            'salesperson': c.salesperson,
        }
        for c in customers
    ])

@db_bp.route('/customers/<string:customer_id>', methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])
@token_required
def handle_single_customer(customer_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'GET':
        # Fetch form submissions - using only CustomerFormData to avoid duplicates
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
            'form_submissions': form_submissions  # Single source - no duplicates
        })
    
    elif request.method == 'PUT':
        data = request.json
        customer.name = data.get('name', customer.name)
        customer.address = data.get('address', customer.address)
        customer.phone = data.get('phone', customer.phone)
        customer.email = data.get('email', customer.email)
        customer.contact_made = data.get('contact_made', customer.contact_made)
        customer.preferred_contact_method = data.get('preferred_contact_method', customer.preferred_contact_method)
        customer.marketing_opt_in = data.get('marketing_opt_in', customer.marketing_opt_in)
        customer.status = data.get('status', customer.status)
        customer.stage = data.get('stage', customer.stage)
        customer.notes = data.get('notes', customer.notes)
        customer.updated_by = request.current_user.email if hasattr(request, 'current_user') else data.get('updated_by', 'System')
        customer.salesperson = data.get('salesperson', customer.salesperson)
        customer.project_types = data.get('project_types', customer.project_types)
        
        if data.get('date_of_measure'):
            customer.date_of_measure = datetime.strptime(data['date_of_measure'], '%Y-%m-%d').date()
        
        # Auto-extract postcode if address changed
        if 'address' in data:
            customer.postcode = customer.extract_postcode_from_address()
        
        db.session.commit()
        return jsonify({'message': 'Customer updated successfully'})
    
    elif request.method == 'DELETE':
        db.session.delete(customer)
        db.session.commit()
        return jsonify({'message': 'Customer deleted successfully'})

@db_bp.route('/customers/<string:customer_id>/sync-stage', methods=['POST'])
def sync_customer_stage(customer_id):
    """Sync customer stage with their primary job's stage"""
    customer = Customer.query.get_or_404(customer_id)
    old_stage = customer.stage
    customer.update_stage_from_job()
    
    return jsonify({
        'message': 'Customer stage synchronized',
        'old_stage': old_stage,
        'new_stage': customer.stage
    })

# Keep existing quotation routes unchanged
@db_bp.route('/quotations', methods=['GET', 'POST', 'OPTIONS'])
@token_required  # ADD THIS DECORATOR
def handle_quotations():
    """
    GET: Retrieve quotations (optionally filtered by customer_id)
    POST: Create a new quotation with items
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    if request.method == 'POST':
        try:
            data = request.json
            print(f"[QUOTATION POST] Received data: {json.dumps(data, indent=2)}")  # Debug log
            
            # Validate required fields
            if 'customer_id' not in data:
                return jsonify({'error': 'customer_id is required'}), 400
            if 'total' not in data:
                return jsonify({'error': 'total is required'}), 400
            
            # Convert customer_id to string if it's an integer (UUID format expected)
            customer_id = str(data['customer_id'])
            
            # Verify customer exists
            customer = Customer.query.get(customer_id)
            if not customer:
                return jsonify({'error': f'Customer with id {customer_id} not found'}), 404
            
            print(f"[QUOTATION POST] Creating quotation for customer: {customer.name} (ID: {customer_id})")
            
            # Get user role for auto-approval logic
            user = getattr(request, 'current_user', None)
            is_manager = user and user.role == 'Manager'
            auto_approve = data.get('auto_approve', False) or is_manager
            
            # Create quotation
            quotation = Quotation(
                customer_id=customer_id,
                total=float(data['total']),
                notes=data.get('notes', ''),
                status='Approved' if auto_approve else 'Draft'
            )
            
            db.session.add(quotation)
            db.session.flush()  # Get the quotation.id
            
            print(f"[QUOTATION POST] Created quotation ID: {quotation.id}")
            
            # Add items
            items_created = 0
            for item_data in data.get('items', []):
                q_item = QuotationItem(
                    quotation_id=quotation.id,
                    item=item_data.get('item', ''),
                    description=item_data.get('description', ''),
                    color=item_data.get('color', ''),
                    amount=float(item_data.get('amount', 0))
                )
                db.session.add(q_item)
                items_created += 1
            
            print(f"[QUOTATION POST] Created {items_created} items")
            
            # Commit everything
            db.session.commit()
            
            print(f"[QUOTATION POST] Successfully saved quotation {quotation.id} for customer {customer_id}")
            
            # Return response
            return jsonify({
                'quotation_id': quotation.id,
                'id': quotation.id,
                'customer_id': customer_id,
                'total': float(quotation.total),
                'approval_status': 'approved' if auto_approve else 'pending',
                'message': 'Quotation created successfully'
            }), 201
            
        except KeyError as e:
            print(f"[QUOTATION POST ERROR] Missing key: {e}")
            return jsonify({'error': f'Missing required field: {str(e)}'}), 400
        except Exception as e:
            db.session.rollback()
            print(f"[QUOTATION POST ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    # GET request - retrieve quotations
    customer_id = request.args.get('customer_id', type=str)
    
    print(f"[QUOTATION GET] Fetching quotations for customer_id: {customer_id if customer_id else 'ALL'}")
    
    if customer_id:
        quotations = Quotation.query.filter_by(customer_id=customer_id).order_by(Quotation.created_at.desc()).all()
        print(f"[QUOTATION GET] Found {len(quotations)} quotations for customer {customer_id}")
    else:
        quotations = Quotation.query.order_by(Quotation.created_at.desc()).all()
        print(f"[QUOTATION GET] Found {len(quotations)} total quotations")
    
    result = [
        {
            'id': q.id,
            'customer_id': q.customer_id,
            'customer_name': q.customer.name if q.customer else None,
            'total': float(q.total) if q.total else 0,
            'status': q.status,
            'notes': q.notes,
            'created_at': q.created_at.isoformat() if q.created_at else None,
            'updated_at': q.updated_at.isoformat() if q.updated_at else None,
            'items': [
                {
                    'id': i.id,
                    'item': i.item,
                    'description': i.description,
                    'color': i.color,
                    'amount': float(i.amount) if i.amount else 0
                } for i in q.items
            ]
        } for q in quotations
    ]
    
    print(f"[QUOTATION GET] Returning {len(result)} quotations")
    return jsonify(result)


@db_bp.route('/quotations/<int:quotation_id>', methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])
@token_required  # ADD THIS DECORATOR
def handle_single_quotation(quotation_id):
    """Handle single quotation operations"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    quotation = Quotation.query.get_or_404(quotation_id)

    if request.method == 'GET':
        return jsonify({
            'id': quotation.id,
            'customer_id': quotation.customer_id,
            'customer_name': quotation.customer.name if quotation.customer else None,
            'total': float(quotation.total) if quotation.total else 0,
            'status': quotation.status,
            'notes': quotation.notes,
            'created_at': quotation.created_at.isoformat() if quotation.created_at else None,
            'updated_at': quotation.updated_at.isoformat() if quotation.updated_at else None,
            'items': [
                {
                    'id': i.id,
                    'item': i.item,
                    'description': i.description,
                    'color': i.color,
                    'amount': float(i.amount) if i.amount else 0
                } for i in quotation.items
            ]
        })

    elif request.method == 'PUT':
        data = request.json
        quotation.total = data.get('total', quotation.total)
        quotation.notes = data.get('notes', quotation.notes)
        quotation.status = data.get('status', quotation.status)

        if 'items' in data:
            # Delete existing items
            QuotationItem.query.filter_by(quotation_id=quotation.id).delete()
            
            # Add new items
            for item_data in data['items']:
                q_item = QuotationItem(
                    quotation_id=quotation.id,
                    item=item_data.get('item', ''),
                    description=item_data.get('description', ''),
                    color=item_data.get('color', ''),
                    amount=float(item_data.get('amount', 0))
                )
                db.session.add(q_item)

        db.session.commit()
        return jsonify({'message': 'Quotation updated successfully'})

    elif request.method == 'DELETE':
        db.session.delete(quotation)
        db.session.commit()
        return jsonify({'message': 'Quotation deleted successfully'})


@db_bp.route('/quotations/<int:quotation_id>/pdf', methods=['GET', 'OPTIONS'])
@token_required
def get_quotation_pdf(quotation_id):
    """Generate and return quotation PDF"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        quotation = Quotation.query.get_or_404(quotation_id)
        
        # TODO: Implement PDF generation
        # For now, return a placeholder response
        return jsonify({
            'error': 'PDF generation not yet implemented',
            'quotation_id': quotation_id
        }), 501
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Additional routes to add to your db_routes.py file

@db_bp.route('/jobs', methods=['GET', 'POST', 'OPTIONS'])
@token_required
def handle_jobs():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    if request.method == 'POST':
        data = request.json
        
        # Create new job
        job = Job(
            customer_id=data['customer_id'],
            job_reference=data.get('job_reference'),
            job_name=data.get('job_name'),
            job_type=data.get('job_type', 'Kitchen'),
            stage=data.get('stage', 'Lead'),  # Default to Lead
            priority=data.get('priority', 'Medium'),
            quote_price=data.get('quote_price'),
            agreed_price=data.get('agreed_price'),
            sold_amount=data.get('sold_amount'),
            deposit1=data.get('deposit1'),
            deposit2=data.get('deposit2'),
            installation_address=data.get('installation_address'),
            notes=data.get('notes'),
            salesperson_name=data.get('salesperson_name'),
            assigned_team_name=data.get('assigned_team_name'),
            primary_fitter_name=data.get('primary_fitter_name')
        )
        
        # Parse dates
        if data.get('delivery_date'):
            job.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d')
        if data.get('measure_date'):
            job.measure_date = datetime.strptime(data['measure_date'], '%Y-%m-%d')
        if data.get('completion_date'):
            job.completion_date = datetime.strptime(data['completion_date'], '%Y-%m-%d')
        if data.get('deposit_due_date'):
            job.deposit_due_date = datetime.strptime(data['deposit_due_date'], '%Y-%m-%d')
        
        db.session.add(job)
        db.session.commit()
        
        # Update customer stage to match job stage if this is their first/primary job
        customer = Customer.query.get(job.customer_id)
        if customer:
            customer.update_stage_from_job()
        
        return jsonify({
            'id': job.id,
            'message': 'Job created successfully'
        }), 201
    
    # GET all jobs
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return jsonify([
        {
            'id': j.id,
            'customer_id': j.customer_id,
            'job_reference': j.job_reference,
            'job_name': j.job_name,
            'job_type': j.job_type,
            'stage': j.stage,
            'priority': j.priority,
            'quote_price': float(j.quote_price) if j.quote_price else None,
            'agreed_price': float(j.agreed_price) if j.agreed_price else None,
            'sold_amount': float(j.sold_amount) if j.sold_amount else None,
            'deposit1': float(j.deposit1) if j.deposit1 else None,
            'deposit2': float(j.deposit2) if j.deposit2 else None,
            'delivery_date': j.delivery_date.isoformat() if j.delivery_date else None,
            'measure_date': j.measure_date.isoformat() if j.measure_date else None,
            'completion_date': j.completion_date.isoformat() if j.completion_date else None,
            'installation_address': j.installation_address,
            'notes': j.notes,
            'salesperson_name': j.salesperson_name,
            'assigned_team_name': j.assigned_team_name,
            'primary_fitter_name': j.primary_fitter_name,
            'created_at': j.created_at.isoformat() if j.created_at else None,
            'updated_at': j.updated_at.isoformat() if j.updated_at else None,
        }
        for j in jobs
    ])

@db_bp.route('/jobs/<string:job_id>', methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])
@token_required
def handle_single_job(job_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'GET':
        return jsonify({
            'id': job.id,
            'customer_id': job.customer_id,
            'job_reference': job.job_reference,
            'job_name': job.job_name,
            'job_type': job.job_type,
            'stage': job.stage,
            'priority': job.priority,
            'quote_price': float(job.quote_price) if job.quote_price else None,
            'agreed_price': float(job.agreed_price) if job.agreed_price else None,
            'sold_amount': float(job.sold_amount) if job.sold_amount else None,
            'deposit1': float(job.deposit1) if job.deposit1 else None,
            'deposit2': float(job.deposit2) if job.deposit2 else None,
            'delivery_date': job.delivery_date.isoformat() if job.delivery_date else None,
            'measure_date': job.measure_date.isoformat() if job.measure_date else None,
            'completion_date': job.completion_date.isoformat() if job.completion_date else None,
            'deposit_due_date': job.deposit_due_date.isoformat() if job.deposit_due_date else None,
            'installation_address': job.installation_address,
            'notes': job.notes,
            'salesperson_name': job.salesperson_name,
            'assigned_team_name': job.assigned_team_name,
            'primary_fitter_name': job.primary_fitter_name,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'updated_at': job.updated_at.isoformat() if job.updated_at else None,
        })
    
    elif request.method == 'PUT':
        data = request.json
        
        # Update job fields
        job.job_reference = data.get('job_reference', job.job_reference)
        job.job_name = data.get('job_name', job.job_name)
        job.job_type = data.get('job_type', job.job_type)
        job.stage = data.get('stage', job.stage)
        job.priority = data.get('priority', job.priority)
        job.quote_price = data.get('quote_price', job.quote_price)
        job.agreed_price = data.get('agreed_price', job.agreed_price)
        job.sold_amount = data.get('sold_amount', job.sold_amount)
        job.deposit1 = data.get('deposit1', job.deposit1)
        job.deposit2 = data.get('deposit2', job.deposit2)
        job.installation_address = data.get('installation_address', job.installation_address)
        job.notes = data.get('notes', job.notes)
        job.salesperson_name = data.get('salesperson_name', job.salesperson_name)
        job.assigned_team_name = data.get('assigned_team_name', job.assigned_team_name)
        job.primary_fitter_name = data.get('primary_fitter_name', job.primary_fitter_name)
        
        # Update dates
        if 'delivery_date' in data and data['delivery_date']:
            job.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d')
        if 'measure_date' in data and data['measure_date']:
            job.measure_date = datetime.strptime(data['measure_date'], '%Y-%m-%d')
        if 'completion_date' in data and data['completion_date']:
            job.completion_date = datetime.strptime(data['completion_date'], '%Y-%m-%d')
        if 'deposit_due_date' in data and data['deposit_due_date']:
            job.deposit_due_date = datetime.strptime(data['deposit_due_date'], '%Y-%m-%d')
        
        db.session.commit()
        
        # Update customer stage if this job's stage changed
        if 'stage' in data:
            customer = Customer.query.get(job.customer_id)
            if customer:
                customer.update_stage_from_job()
        
        return jsonify({'message': 'Job updated successfully'})
    
    elif request.method == 'DELETE':
        db.session.delete(job)
        db.session.commit()
        
        # Update customer stage after job deletion
        customer = Customer.query.get(job.customer_id)
        if customer:
            customer.update_stage_from_job()
        
        return jsonify({'message': 'Job deleted successfully'})

@db_bp.route('/pipeline', methods=['GET', 'OPTIONS'])
@token_required
def get_pipeline_data():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    """
    Specialized endpoint that returns combined customer/job data optimized for the pipeline view
    """
    # Fetch customers with their jobs
    customers = Customer.query.all()
    jobs = Job.query.all()
    
    # Create a map for quick job lookup
    jobs_by_customer = {}
    for job in jobs:
        if job.customer_id not in jobs_by_customer:
            jobs_by_customer[job.customer_id] = []
        jobs_by_customer[job.customer_id].append(job)
    
    pipeline_items = []
    
    for customer in customers:
        customer_jobs = jobs_by_customer.get(customer.id, [])
        
        if not customer_jobs:
            # Customer without jobs
            pipeline_items.append({
                'id': f'customer-{customer.id}',
                'type': 'customer',
                'customer': {
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
                    'stage': customer.stage,
                    'notes': customer.notes,
                    'project_types': customer.project_types,
                    'salesperson': customer.salesperson,
                    'status': customer.status,
                    'created_at': customer.created_at.isoformat() if customer.created_at else None,
                }
            })
        else:
            # Customer with jobs - create item for each job
            for job in customer_jobs:
                # Calculate deposit payment status from Payment records
                # For now, defaulting to False - you can implement payment checking logic
                deposit1_paid = False
                deposit2_paid = False
                
                # You could add payment checking here:
                # payments = Payment.query.filter_by(job_id=job.id).all()
                # deposit1_paid = any(p.amount == job.deposit1 and p.cleared for p in payments)
                # deposit2_paid = any(p.amount == job.deposit2 and p.cleared for p in payments)
                
                pipeline_items.append({
                    'id': f'job-{job.id}',
                    'type': 'job',
                    'customer': {
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
                        'stage': customer.stage,
                        'notes': customer.notes,
                        'project_types': customer.project_types,
                        'salesperson': customer.salesperson,
                        'status': customer.status,
                        'created_at': customer.created_at.isoformat() if customer.created_at else None,
                    },
                    'job': {
                        'id': job.id,
                        'customer_id': job.customer_id,
                        'job_reference': job.job_reference,
                        'job_name': job.job_name,
                        'job_type': job.job_type,
                        'stage': job.stage,
                        'priority': job.priority,
                        'quote_price': float(job.quote_price) if job.quote_price else None,
                        'agreed_price': float(job.agreed_price) if job.agreed_price else None,
                        'sold_amount': float(job.sold_amount) if job.sold_amount else None,
                        'deposit1': float(job.deposit1) if job.deposit1 else None,
                        'deposit2': float(job.deposit2) if job.deposit2 else None,
                        'deposit1_paid': deposit1_paid,
                        'deposit2_paid': deposit2_paid,
                        'delivery_date': job.delivery_date.isoformat() if job.delivery_date else None,
                        'measure_date': job.measure_date.isoformat() if job.measure_date else None,
                        'completion_date': job.completion_date.isoformat() if job.completion_date else None,
                        'installation_address': job.installation_address,
                        'notes': job.notes,
                        'salesperson_name': job.salesperson_name,
                        'assigned_team_name': job.assigned_team_name,
                        'primary_fitter_name': job.primary_fitter_name,
                        'created_at': job.created_at.isoformat() if job.created_at else None,
                        'updated_at': job.updated_at.isoformat() if job.updated_at else None,
                    }
                })
    
    return jsonify(pipeline_items)


@db_bp.route('/fitters', methods=['GET'])
def get_fitters():
    """Get all active fitters for team member dropdown"""
    try:
        fitters = Fitter.query.filter_by(active=True).all()
        return jsonify([
            {
                'id': f.id,
                'name': f.name,
                'role': f.team.name if f.team else 'Unassigned',
                'team_id': f.team_id
            }
            for f in fitters
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@db_bp.route('/jobs/available', methods=['GET'])
def get_available_jobs():
    """Get jobs that are ready for scheduling"""
    try:
        schedulable_stages = ['Accepted', 'Production', 'Delivery', 'Installation']
        jobs = Job.query.filter(Job.stage.in_(schedulable_stages)).all()
        
        return jsonify([
            {
                'id': j.id,
                'job_reference': j.job_reference,
                'customer_name': j.customer.name,
                'customer_id': j.customer_id,
                'job_type': j.job_type,
                'stage': j.stage,
                'installation_address': j.installation_address or j.customer.address,
                'priority': j.priority
            }
            for j in jobs
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@db_bp.route('/customers/active', methods=['GET'])
def get_active_customers():
    """Get all active customers for dropdown"""
    try:
        customers = Customer.query.filter_by(status='Active').order_by(Customer.name).all()
        return jsonify([
            {
                'id': c.id,
                'name': c.name,
                'address': c.address,
                'phone': c.phone,
                'stage': c.stage
            }
            for c in customers
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
@db_bp.route('/customers/<string:customer_id>/stage', methods=['PATCH', 'OPTIONS'])
@token_required
def update_customer_stage(customer_id):
    """Update customer stage - optimized endpoint for drag and drop"""
    if request.method == 'OPTIONS': # Handle OPTIONS
        return jsonify({}), 200
    try:
        customer = Customer.query.get_or_404(customer_id)
        
        data = request.json
        updated_by_user = request.current_user.email if hasattr(request, 'current_user') else data.get('updated_by', 'System')
        new_stage = data.get('stage')
        reason = data.get('reason', 'Stage updated via drag and drop')
        
        if not new_stage:
            return jsonify({'error': 'Stage is required'}), 400
        
        # Valid stages list (ensure 'Accepted' is exactly like this)
        valid_stages = [
            "Lead", "Survey", "Design", "Quote", "Consultation", "Quoted", 
            "Accepted", "OnHold", "Production", "Delivery", "Installation", 
            "Complete", "Remedial", "Cancelled" 
        ]
        
        if new_stage not in valid_stages:
            return jsonify({'error': 'Invalid stage'}), 400
        
        # Update stage
        old_stage = customer.stage

        # --- START OF FIX ---
        # Only proceed if the stage actually changed
        if old_stage == new_stage:
            return jsonify({'message': 'Stage not changed'}), 200
        # --- END OF FIX ---
        
        customer.stage = new_stage
        customer.updated_by = updated_by_user
        customer.updated_at = datetime.utcnow()
        
        # Optional: Add to notes for audit trail
        note_entry = f"\n[{datetime.utcnow().isoformat()}] Stage changed from {old_stage} to {new_stage}. Reason: {reason}"
        if customer.notes:
            customer.notes += note_entry
        else:
            customer.notes = note_entry

        # --- Notification Logic ---
        notification_to_add = None # Prepare a variable for the notification
        if new_stage == 'Accepted':
            current_app.logger.info(f"✅ Stage changed to Accepted for job {customer_id}. Preparing notification.") # Log info
            notification_to_add = ProductionNotification(
                job_id=customer.id,  # Use customer ID as job_id for customer-only items
                customer_id=customer.id,
                message=f"customer '{customer.name or customer.id}' moved to Accepted",
                moved_by=updated_by_user 
            )
            db.session.add(notification_to_add) # Add notification to the session
        # --- End Notification Logic ---

        # --- START OF FIX 2 ---
        # Also update any jobs that are linked to this customer AND are in the same old stage
        # This is for when a 'customer' card is dragged, and we want its jobs to follow.
        try:
            linked_jobs = Job.query.filter_by(customer_id=customer.id, stage=old_stage).all()
            for job in linked_jobs:
                job.stage = new_stage
                job.updated_at = datetime.utcnow()
                note_entry_job = f"\n[{datetime.utcnow().isoformat()}] Stage synced from {old_stage} to {new_stage} by {updated_by_user}. Reason: Parent customer moved."
                if job.notes:
                    job.notes += note_entry_job
                else:
                    job.notes = note_entry_job
                current_app.logger.info(f"🔄 Queued sync for job {job.id} stage to {new_stage}.")
        except Exception as e:
            current_app.logger.error(f"⚠️ Error queueing job sync for customer {customer_id}: {e}")
        # --- END OF FIX 2 ---
        
        # CRITICAL: Commit the changes to the database
        db.session.commit()
        current_app.logger.info(f"💾 Committed changes for customer {customer_id}. New stage: {new_stage}.")
        
        return jsonify({
            'message': 'Stage updated successfully',
            'customer_id': customer.id,
            'old_stage': old_stage,
            'new_stage': new_stage
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating customer stage for {customer_id}: {e}") # Log error
        return jsonify({'error': str(e)}), 500


@db_bp.route('/jobs/<string:job_id>/stage', methods=['PATCH', 'OPTIONS'])
@token_required
def update_job_stage(job_id):
    """Update job stage - optimized endpoint for drag and drop"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    job = Job.query.get_or_404(job_id)
    
    data = request.json
    updated_by_user = request.current_user.email if hasattr(request, 'current_user') else data.get('updated_by', 'System')
    new_stage = data.get('stage')
    reason = data.get('reason', 'Stage updated via drag and drop')
    
    if not new_stage:
        return jsonify({'error': 'Stage is required'}), 400
    
    # Valid stages list (ensure 'Accepted' is exactly like this)
    valid_stages = [
        "Lead", "Survey", "Design", "Quote", "Consultation", "Quoted", 
        "Accepted", "OnHold", "Production", "Delivery", "Installation", 
        "Complete", "Remedial", "Cancelled" 
    ]
    
    if new_stage not in valid_stages:
        return jsonify({'error': 'Invalid stage'}), 400
    
    old_stage = job.stage
    
    # Only proceed if the stage actually changed
    if old_stage == new_stage:
        return jsonify({'message': 'Stage not changed'}), 200

    try:
        # Update stage
        job.stage = new_stage
        job.updated_at = datetime.utcnow()
        
        # Add to notes for audit trail
        note_entry = f"\n[{datetime.utcnow().isoformat()}] Stage changed from {old_stage} to {new_stage} by {updated_by_user}. Reason: {reason}"
        if job.notes:
            job.notes += note_entry
        else:
            job.notes = note_entry
        
        # --- Notification Logic ---
        notification_to_add = None # Prepare a variable for the notification
        if new_stage == 'Accepted':
            current_app.logger.info(f"✅ Stage changed to Accepted for job {job_id}. Preparing notification.") # Log info
            notification_to_add = ProductionNotification(
                job_id=job.id,
                customer_id=job.customer_id,
                message=f"Job '{job.job_name or job.job_reference or job.id}' moved to Accepted",
                moved_by=updated_by_user 
            )
            db.session.add(notification_to_add) # Add notification to the session
        # --- End Notification Logic ---
        
        # --- START OF FIX ---
        # ALSO update the parent customer's stage to keep them in sync.
        try:
            customer = Customer.query.get(job.customer_id)
            if customer and customer.stage != new_stage:
                customer.stage = new_stage
                customer.updated_at = datetime.utcnow()
                note_entry_cust = f"\n[{datetime.utcnow().isoformat()}] Stage synced from {old_stage} to {new_stage} by {updated_by_user}. Reason: Linked job moved."
                if customer.notes:
                    customer.notes += note_entry_cust
                else:
                    customer.notes = note_entry_cust
                current_app.logger.info(f"🔄 Queued sync for customer {customer.id} stage to {new_stage}.")
        except Exception as e:
            # Log this error, but don't fail the whole request
            current_app.logger.error(f"⚠️ Error queueing customer stage sync for job {job_id}: {e}")
        # --- END OF FIX ---


        # Commit ALL changes (stage update, notification, AND customer sync) together
        db.session.commit() 
        current_app.logger.info(f"💾 Committed changes for job {job_id}. New stage: {new_stage}.")

        return jsonify({
            'message': 'Stage updated successfully',
            'job_id': job.id,
            'old_stage': old_stage,
            'new_stage': new_stage
        }), 200

    except Exception as e:
        db.session.rollback() # Rollback ALL changes if anything fails
        current_app.logger.error(f"❌ Error updating job stage for {job_id}: {e}") # Log error
        return jsonify({'error': f'Failed to update stage: {str(e)}'}), 500