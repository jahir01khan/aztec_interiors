from flask import Blueprint, request, jsonify
from database import db
from models import Assignment, Job, Customer
from datetime import datetime
from utils.google_calendar_utils import create_calendar_event, update_calendar_event, delete_calendar_event

# Create blueprint
assignment_bp = Blueprint('assignments', __name__)

@assignment_bp.route('/assignments', methods=['GET', 'POST'])
def handle_assignments():
    if request.method == 'POST':
        data = request.json
        
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
            
            # Create assignment - team_member is just a string now
            assignment = Assignment(
                type=data.get('type', 'job'),
                title=data.get('title', ''),
                date=assignment_date,
                team_member=data.get('team_member', ''),  # Store as string
                job_id=data.get('job_id'),
                customer_id=data.get('customer_id'),
                start_time=start_time,
                end_time=end_time,
                estimated_hours=estimated_hours,
                notes=data.get('notes', ''),
                priority=data.get('priority', 'Medium'),
                status=data.get('status', 'Scheduled'),
                created_by=data.get('created_by', 'System')
            )
            
            db.session.add(assignment)
            db.session.commit()
            
            # Create Google Calendar event
            try:
                event_id = create_calendar_event(assignment)
                assignment.calendar_event_id = event_id
                db.session.commit()
            except Exception as cal_err:
                print(f"Google Calendar event creation failed: {cal_err}")
            
            return jsonify({
                'message': 'Assignment created successfully',
                'assignment': assignment.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400
    
    # GET all assignments
    assignments = Assignment.query.order_by(Assignment.date.desc()).all()
    return jsonify([a.to_dict() for a in assignments])


@assignment_bp.route('/assignments/<string:assignment_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_single_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if request.method == 'GET':
        return jsonify(assignment.to_dict())
    
    elif request.method == 'PUT':
        data = request.json
        
        try:
            # Update fields
            if 'type' in data:
                assignment.type = data['type']
            if 'title' in data:
                assignment.title = data['title']
            if 'date' in data:
                assignment.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
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
            if 'team_member' in data:
                assignment.team_member = data['team_member']  # Just update the string
            
            assignment.updated_by = data.get('updated_by', 'System')
            assignment.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Update Google Calendar event if exists
            if assignment.calendar_event_id:
                try:
                    update_calendar_event(assignment.calendar_event_id, assignment)
                except Exception as cal_err:
                    print(f"Google Calendar event update failed: {cal_err}")
            
            return jsonify({
                'message': 'Assignment updated successfully',
                'assignment': assignment.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            # Delete Google Calendar event if exists
            if assignment.calendar_event_id:
                try:
                    delete_calendar_event(assignment.calendar_event_id)
                except Exception as cal_err:
                    print(f"Google Calendar event deletion failed: {cal_err}")
            
            db.session.delete(assignment)
            db.session.commit()
            return jsonify({'message': 'Assignment deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400


@assignment_bp.route('/assignments/by-date-range', methods=['GET'])
def get_assignments_by_date_range():
    """Get assignments within a date range"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'start_date and end_date are required'}), 400
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        assignments = Assignment.query.filter(
            Assignment.date >= start,
            Assignment.date <= end
        ).order_by(Assignment.date).all()
        
        return jsonify([a.to_dict() for a in assignments])
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@assignment_bp.route('/jobs/available', methods=['GET'])
def get_available_jobs():
    """Get jobs that are ready to be scheduled"""
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
def get_active_customers():
    """Get active customers"""
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