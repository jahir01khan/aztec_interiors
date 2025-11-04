from flask import Blueprint, request, jsonify
from datetime import datetime
from ..models import CustomerFormData, User, Customer, ApprovalNotification # <-- User and Customer are imported here
from .auth_routes import token_required

# 👈 NEW IMPORTS: Required for SQLAlchemy usage
from ..db import SessionLocal 
from ..models import Assignment, Job # Assuming Assignment and Job models are used and defined in ..models
# REMOVED: from ..database import db 

from ..utils.google_calendar_utils import create_calendar_event, update_calendar_event, delete_calendar_event

# Create blueprint
assignment_bp = Blueprint('assignments', __name__)

@assignment_bp.route('/assignments', methods=['GET', 'POST'])
@token_required
def handle_assignments():
    current_user = request.current_user
    
    if request.method == 'POST':
        data = request.json
        session = SessionLocal() # 👈 Start session for POST
        
        try:
            # Parse date
            assignment_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            
            # Parse times if provided
            start_time = None
            end_time = None
            if data.get('start_time'):
                start_time = datetime.strptime(data['start_time'], '%H:%M').time()
            if data.get('end_time'):
                end_time = datetime.strptime(data['end_time'], '%H:%M').time()
            
            # Calculate hours
            estimated_hours = data.get('estimated_hours')
            if isinstance(estimated_hours, str):
                estimated_hours = float(estimated_hours) if estimated_hours else None

            user_id = data.get('user_id')
            team_member_name = None
            if user_id:
                # Query using the active session
                assigned_user = session.get(User, user_id) 
                if assigned_user:
                    team_member_name = assigned_user.full_name # Use full_name property if available
            
            # Create assignment
            assignment = Assignment(
                type=data.get('type', 'job'),
                title=data.get('title', ''),
                date=assignment_date,
                user_id=data.get('user_id'),
                team_member=team_member_name,
                created_by=current_user.id,
                # Assuming created_by_name field exists
                # created_by_name=current_user.get_full_name(), 
                # Assuming job_type field exists
                # job_type=data.get('job_type'), 
                job_id=data.get('job_id'),
                customer_id=data.get('customer_id'),
                start_time=start_time,
                end_time=end_time,
                estimated_hours=estimated_hours,
                notes=data.get('notes', ''),
                priority=data.get('priority', 'Medium'),
                status=data.get('status', 'Scheduled')
            )
            
            session.add(assignment)
            session.commit() # 👈 Commit after creating assignment
            
            # --- NEW GOOGLE SYNC LOGIC (CREATE) ---
            should_sync = (current_user.role == 'Manager' and assignment.user_id == current_user.id)
            
            if should_sync:
                try:
                    event_id = create_calendar_event(assignment)
                    assignment.calendar_event_id = event_id
                    # Persist event ID using the same session
                    session.commit() 
                except Exception as cal_err:
                    print(f"Google Calendar event creation failed: {cal_err}")

            return jsonify({
                'message': 'Assignment created successfully',
                'assignment': assignment.to_dict()
            }), 201

        except Exception as e:
            session.rollback() # 👈 Rollback on error
            return jsonify({'error': str(e)}), 400
        finally:
            session.close() # 👈 Close session
    
    # -------------------- GET --------------------
    if request.method == 'GET':
        # Query functions like .all() handle their own session implicitly (via base query configuration)
        current_user_id = request.current_user.id
        
        if current_user.role == 'Manager':
            # Manager gets all assignments
            assignments = Assignment.query.order_by(Assignment.date.desc()).all()
        else:
            # Non-manager only gets their own assignments
            assignments = Assignment.query.filter_by(
                user_id=current_user_id
            ).order_by(Assignment.date.desc()).all()

        return jsonify([a.to_dict() for a in assignments])


@assignment_bp.route('/assignments/<string:assignment_id>', methods=['GET', 'PUT', 'DELETE'])
@token_required
def handle_single_assignment(assignment_id):
    current_user = request.current_user
    
    # Use SessionLocal to get the object for PUT/DELETE/GET (if needed outside base query)
    # Using base query here for simplicity, assuming it's configured for the thread
    assignment = Assignment.query.get_or_404(assignment_id) 
    
    # --- Authorization Check (for PUT/DELETE) ---
    if request.method in ['PUT', 'DELETE']:
        if current_user.role != 'Manager' and assignment.user_id != current_user.id:
            # Allow status change only if assigned user is changing their own status (Task 6)
            if request.method == 'PUT' and list(request.json.keys()) == ['status']:
                 pass 
            else:
                return jsonify({'error': 'Unauthorized'}), 403

    
    # -------------------- GET --------------------
    if request.method == 'GET':
        # Users should only be able to GET their own assignments (checked above for consistency)
        if current_user.role != 'Manager' and assignment.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        return jsonify(assignment.to_dict())
    
    # -------------------- PUT --------------------
    elif request.method == 'PUT':
        data = request.json
        session = SessionLocal() # 👈 Start session for PUT

        try:
            # Use session.get() to attach object to the transaction
            assignment = session.get(Assignment, assignment_id) 
            if not assignment:
                return jsonify({'error': 'Assignment not found'}), 404

            if 'type' in data:
                assignment.type = data['type']
            if 'title' in data:
                assignment.title = data['title']
            if 'date' in data:
                assignment.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            # if 'job_type' in data: # Assuming job_type field exists
            #     assignment.job_type = data['job_type']
            if 'job_id' in data:
                assignment.job_id = data['job_id']
            if 'customer_id' in data:
                assignment.customer_id = data['customer_id']
            if 'start_time' in data:
                assignment.start_time = datetime.strptime(data['start_time'], '%H:%M').time() if data['start_time'] else None
            if 'end_time' in data:
                assignment.end_time = datetime.strptime(data['end_time'], '%H:%M').time() if data['end_time'] else None
            if 'estimated_hours' in data:
                estimated_hours = data['estimated_hours']
                assignment.estimated_hours = float(estimated_hours) if isinstance(estimated_hours, str) else estimated_hours
            if 'notes' in data:
                assignment.notes = data['notes']
            if 'priority' in data:
                assignment.priority = data['priority']
            if 'status' in data:
                assignment.status = data['status']
            if 'user_id' in data:
                assignment.user_id = data['user_id']
                # Update team_member name if user_id changes
                new_user = session.get(User, data['user_id'])
                if new_user:
                    assignment.team_member = new_user.full_name
            
            assignment.updated_by = current_user.id
            # assignment.updated_by_name = current_user.get_full_name() # Assuming updated_by_name field exists
            assignment.updated_at = datetime.utcnow()
            
            session.commit() # 👈 Commit transaction

            # --- NEW GOOGLE SYNC LOGIC (UPDATE) ---
            should_sync = (current_user.role == 'Manager' and assignment.user_id == current_user.id)

            if should_sync and assignment.calendar_event_id:
                try:
                    update_calendar_event(assignment.calendar_event_id, assignment)
                except Exception as cal_err:
                    print(f"Google Calendar event update failed: {cal_err}")
            
            return jsonify({
                'message': 'Assignment updated successfully',
                'assignment': assignment.to_dict()
            })
            
        except Exception as e:
            session.rollback() # 👈 Rollback on error
            return jsonify({'error': str(e)}), 400
        finally:
            session.close() # 👈 Close session
    
    # -------------------- DELETE --------------------
    elif request.method == 'DELETE':
        session = SessionLocal() # 👈 Start session for DELETE
        try:
            # Use session.get() to attach object to the transaction
            assignment = session.get(Assignment, assignment_id) 
            if not assignment:
                return jsonify({'error': 'Assignment not found'}), 404
            
            # --- NEW GOOGLE SYNC LOGIC (DELETE) ---
            if assignment.calendar_event_id and current_user.role == 'Manager' and assignment.user_id == current_user.id:
                try:
                    delete_calendar_event(assignment.calendar_event_id)
                except Exception as cal_err:
                    print(f"Google Calendar event deletion failed: {cal_err}")
            
            session.delete(assignment)
            session.commit() # 👈 Commit deletion
            
            return jsonify({'message': 'Assignment deleted successfully'})
        
        except Exception as e:
            session.rollback() # 👈 Rollback on error
            return jsonify({'error': str(e)}), 400
        finally:
            session.close() # 👈 Close session


@assignment_bp.route('/assignments/by-date-range', methods=['GET'])
@token_required 
def get_assignments_by_date_range():
    """Get assignments within a date range"""
    current_user = request.current_user
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'start_date and end_date are required'}), 400
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        query = Assignment.query.filter(
            Assignment.date >= start,
            Assignment.date <= end
        )
        
        # Filter by user if not manager
        if current_user.role != 'Manager':
            query = query.filter(Assignment.user_id == current_user.id)
            
        assignments = query.order_by(Assignment.date).all()
        
        return jsonify([a.to_dict() for a in assignments])
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@assignment_bp.route('/jobs/available', methods=['GET'])
@token_required 
def get_available_jobs():
    """Get jobs that are ready to be scheduled"""
    # Note: Job.query is used, assuming implicit session handling for reads.
    jobs = Job.query.filter(
        Job.stage.in_(['ready', 'in_progress', 'confirmed'])
    ).order_by(Job.created_at.desc()).all()
    
    return jsonify([{
        'id': j.id,
        'job_reference': j.job_reference,
        'customer_name': j.customer.name if j.customer else 'Unknown',
        'customer_id': j.customer_id,
        'job_type': j.job_type or 'Interior Design',
        'stage': j.stage
    } for j in jobs])


@assignment_bp.route('/customers/active', methods=['GET'])
@token_required 
def get_active_customers():
    """Get active customers"""
    # Note: Customer.query is used, assuming implicit session handling for reads.
    customers = Customer.query.filter(
        Customer.status == 'Active'
    ).order_by(Customer.name).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'address': c.address,
        'phone': c.phone,
        'stage': c.stage
    } for c in customers])