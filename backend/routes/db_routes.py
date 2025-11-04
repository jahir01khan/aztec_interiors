from flask import Blueprint, request, jsonify, current_app
import json
from datetime import datetime
from ..database import SessionLocal
from ..models import (
    User, Assignment, Customer, CustomerFormData, Fitter, Job,
    ProductionNotification, Quotation, QuotationItem, Project
)
from .auth_helpers import token_required
from sqlalchemy.exc import OperationalError

db_bp = Blueprint('database', __name__)

# ------------------ CUSTOMERS ------------------

@db_bp.route('/customers', methods=['GET', 'POST', 'OPTIONS'])
@token_required
def handle_customers():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    session = SessionLocal()
    try:
        if request.method == 'POST':
            data = request.json
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
                stage=data.get('stage', 'Lead'),
                created_by=getattr(request.current_user, 'email', 'System'),
                status=data.get('status', 'Active'),
                project_types=data.get('project_types', []),
                salesperson=data.get('salesperson'),
            )
            session.add(customer)
            session.commit()
            return jsonify({'id': customer.id, 'message': 'Customer created successfully'}), 201

        # GET all customers
        customers = session.query(Customer).order_by(Customer.created_at.desc()).all()
        return jsonify([c.to_dict(include_projects=False) for c in customers])

    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error handling customers: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@db_bp.route('/customers/<string:customer_id>', methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])
@token_required
def handle_single_customer(customer_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        if request.method == 'GET':
            try:
                form_entries = session.query(CustomerFormData).filter_by(customer_id=customer.id).order_by(CustomerFormData.submitted_at.desc()).all()
            except OperationalError as e:
                current_app.logger.warning(f"Fallback query due to OperationalError: {e}")
                form_entries = []

            form_submissions = []
            for f in form_entries:
                try:
                    raw_data = getattr(f, 'form_data', {})
                    parsed = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    form_submissions.append({
                        "id": getattr(f, 'id', None),
                        "token_used": getattr(f, 'token_used', None),
                        "submitted_at": getattr(f, 'submitted_at', None).isoformat() if getattr(f, 'submitted_at', None) else None,
                        "form_data": parsed,
                        "source": "web_form",
                        "project_id": getattr(f, 'project_id', None),
                        "approval_status": getattr(f, 'approval_status', 'pending'),
                        "approved_by": getattr(f, 'approved_by', None),
                        "approval_date": getattr(f, 'approval_date', None).isoformat() if getattr(f, 'approval_date', None) else None,
                    })
                except Exception as inner_e:
                    current_app.logger.error(f"Error processing form submission {getattr(f, 'id', 'unknown')}: {inner_e}")
                    continue

            customer_data = customer.to_dict(include_projects=True)
            customer_data['form_submissions'] = form_submissions
            return jsonify(customer_data)

        elif request.method == 'PUT':
            data = request.json
            customer.name = data.get('name', customer.name)
            customer.address = data.get('address', customer.address)
            customer.phone = data.get('phone', customer.phone)
            customer.email = data.get('email', customer.email)
            customer.contact_made = data.get('contact_made', customer.contact_made)
            customer.preferred_contact_method = data.get('preferred_contact_method', customer.preferred_contact_method)
            customer.marketing_opt_in = data.get('marketing_opt_in', customer.marketing_opt_in)
            customer.notes = data.get('notes', customer.notes)
            customer.updated_by = getattr(request.current_user, 'email', 'System')
            customer.salesperson = data.get('salesperson', customer.salesperson)
            customer.project_types = data.get('project_types', customer.project_types)
            if data.get('date_of_measure'):
                customer.date_of_measure = datetime.strptime(data['date_of_measure'], '%Y-%m-%d').date()
            if 'stage' in data:
                customer.stage = data.get('stage', customer.stage)
            session.commit()
            return jsonify({'message': 'Customer updated successfully'})

        elif request.method == 'DELETE':
            session.delete(customer)
            session.commit()
            return jsonify({'message': 'Customer deleted successfully'})

    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error handling customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ------------------ CUSTOMER STAGE ------------------

@db_bp.route('/customers/<string:customer_id>/stage', methods=['PATCH', 'OPTIONS'])
@token_required
def update_customer_stage(customer_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        data = request.json
        new_stage = data.get('stage')
        reason = data.get('reason', 'Stage updated via drag and drop')
        if not new_stage:
            return jsonify({'error': 'Stage is required'}), 400

        valid_stages = [
            "Lead", "Survey", "Design", "Quote", "Consultation", "Quoted",
            "Accepted", "OnHold", "Production", "Delivery", "Installation",
            "Complete", "Remedial", "Cancelled"
        ]
        if new_stage not in valid_stages:
            return jsonify({'error': 'Invalid stage'}), 400

        job_count = session.query(Job).filter_by(customer_id=customer.id).count()
        if (customer.projects and len(customer.projects) > 0) or job_count > 0:
            return jsonify({'message': 'Customer stage sync suppressed; projects/jobs exist.'}), 200

        old_stage = customer.stage
        if old_stage == new_stage:
            return jsonify({'message': 'Stage not changed'}), 200

        customer.stage = new_stage
        customer.updated_by = getattr(request.current_user, 'email', 'System')
        customer.updated_at = datetime.utcnow()
        customer.notes = (customer.notes or '') + f"\n[{datetime.utcnow().isoformat()}] Stage changed from {old_stage} to {new_stage}. Reason: {reason}"

        # Add notification for Accepted stage
        if new_stage == 'Accepted':
            linked_job = session.query(Job).filter_by(customer_id=customer.id).first()
            notification = ProductionNotification(
                job_id=linked_job.id if linked_job else None,
                customer_id=customer.id,
                message=f"Customer '{customer.name}' moved to Accepted",
                moved_by=getattr(request.current_user, 'email', 'System')
            )
            session.add(notification)

        session.commit()
        return jsonify({'message': 'Stage updated successfully', 'customer_id': customer.id, 'old_stage': old_stage, 'new_stage': new_stage})

    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error updating customer stage: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ------------------ JOB STAGE ------------------

@db_bp.route('/jobs/<string:job_id>/stage', methods=['PATCH', 'OPTIONS'])
@token_required
def update_job_stage(job_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    session = SessionLocal()
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        data = request.json
        new_stage = data.get('stage')
        reason = data.get('reason', 'Stage updated via drag and drop')
        updated_by_user = getattr(request.current_user, 'email', 'System')

        if not new_stage:
            return jsonify({'error': 'Stage is required'}), 400

        valid_stages = [
            "Lead", "Survey", "Design", "Quote", "Consultation", "Quoted",
            "Accepted", "OnHold", "Production", "Delivery", "Installation",
            "Complete", "Remedial", "Cancelled"
        ]
        if new_stage not in valid_stages:
            return jsonify({'error': 'Invalid stage'}), 400

        old_stage = job.stage
        if old_stage == new_stage:
            return jsonify({'message': 'Stage not changed'}), 200

        job.stage = new_stage
        job.updated_at = datetime.utcnow()
        job.notes = (job.notes or '') + f"\n[{datetime.utcnow().isoformat()}] Stage changed from {old_stage} to {new_stage} by {updated_by_user}. Reason: {reason}"

        # Add notification for Accepted stage
        if new_stage == 'Accepted':
            notification = ProductionNotification(
                job_id=job.id,
                customer_id=job.customer_id,
                message=f"Job '{job.job_name or job.job_reference or job.id}' moved to Accepted",
                moved_by=updated_by_user
            )
            session.add(notification)

        # Sync customer stage if only one job/project linked
        customer = session.query(Customer).filter_by(id=job.customer_id).first()
        if customer:
            job_count = session.query(Job).filter_by(customer_id=customer.id).count()
            total_linked = job_count + (len(customer.projects) if hasattr(customer.projects, '__len__') else 0)
            if total_linked <= 1 and customer.stage != new_stage:
                customer.stage = new_stage
                customer.updated_at = datetime.utcnow()
                customer.notes = (customer.notes or '') + f"\n[{datetime.utcnow().isoformat()}] Stage synced from {old_stage} to {new_stage} by {updated_by_user}. Reason: Linked job moved."
                session.add(customer)

        session.commit()
        return jsonify({'message': 'Stage updated successfully', 'job_id': job.id, 'old_stage': old_stage, 'new_stage': new_stage})

    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error updating job stage: {e}")
        return jsonify({'error': f'Failed to update stage: {str(e)}'}), 500
    finally:
        session.close()


# ------------------ PDF PLACEHOLDER ------------------

@db_bp.route('/pdf/<string:quotation_id>', methods=['GET'])
@token_required
def generate_pdf(quotation_id):
    return jsonify({'error': 'PDF generation not yet implemented'}), 501
