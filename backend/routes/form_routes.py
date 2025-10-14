from flask import Blueprint, request, jsonify, current_app, send_file
from models import db, Customer, CustomerFormData # Assuming these models exist
import secrets
import string
import json
from datetime import datetime, timedelta
from io import BytesIO
from fpdf import FPDF # <-- Now using fpdf2

form_bp = Blueprint("form", __name__)

# In-memory storage for form tokens (for production use Redis/DB)
form_tokens = {}

def generate_secure_token(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# ------------------------------------------------------------------------
# 🛠️ PDF GENERATION HELPERS (Using fpdf2)
# ------------------------------------------------------------------------

class PDF(FPDF):
    """Custom PDF class for consistent headers and footers."""
    def header(self):
        # NOTE: fpdf2 cannot easily embed complex SVGs. We'll use text.
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'AZTEC INTERIORS', 0, 1, 'C')
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'REMEDIAL WORK CHECKLIST', 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

@form_bp.route('/checklists/download-pdf', methods=['POST'])
def download_checklist_pdf():
    """Generates PDF on the server using fpdf2."""
    try:
        data = request.get_json(silent=True) or {}
        
        if not data or not data.get('items'):
            return jsonify({'error': 'Missing form data for PDF generation.'}), 400

        pdf = PDF('P', 'mm', 'A4')
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font('Arial', '', 10)

        # --- 1. Customer and Fitter Details ---
        pdf.set_fill_color(240, 240, 240) 
        pdf.set_draw_color(0, 0, 0) 
        col_width = 190 / 2
        line_height = 6

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, line_height, 'CUSTOMER NAME:', 1, 0, 'L', 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width, line_height, data.get('customerName', 'N/A'), 1, 1, 'L', 0)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, line_height, 'CUSTOMER ADDRESS:', 1, 0, 'L', 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width, line_height, data.get('customerAddress', 'N/A'), 1, 1, 'L', 0)

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, line_height, 'CUSTOMER TEL NO.:', 1, 0, 'L', 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width, line_height, data.get('customerPhone', 'N/A'), 1, 1, 'L', 0)

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, line_height, 'DATE:', 1, 0, 'L', 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width, line_height, data.get('date', 'N/A'), 1, 1, 'L', 0)

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, line_height, 'FITTERS:', 1, 0, 'L', 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width, line_height, data.get('fitters', 'N/A'), 1, 1, 'L', 0)
        
        pdf.ln(10)
        
        # --- 2. Checklist Items Table ---
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, 'Items Required for Remedial Action', 0, 1, 'L')
        pdf.ln(1)
        
        header = ['NO', 'ITEM', 'REMEDIAL ACTION', 'COLOUR', 'SIZE', 'QTY']
        widths = [10, 50, 60, 25, 25, 20]
        
        pdf.set_fill_color(200, 220, 255) 
        pdf.set_font('Arial', 'B', 9)
        
        for i, h in enumerate(header):
            pdf.cell(widths[i], 7, h, 1, 0, 'C', 1)
        pdf.ln()

        # Table Rows
        pdf.set_font('Arial', '', 9)
        pdf.set_fill_color(255, 255, 255)
        
        for index, item in enumerate(data.get('items', [])):
            if not item.get('item') and not item.get('remedialAction'):
                continue
            
            row_data = [
                str(index + 1),
                item.get('item', ''),
                item.get('remedialAction', ''),
                item.get('colour', ''),
                item.get('size', ''),
                str(item.get('qty', '')),
            ]
            
            max_height = 5
            
            # Start multi_cell processing
            x_start = pdf.get_x()
            y_start = pdf.get_y()

            # Item (Multi-line text in column 2)
            pdf.set_xy(x_start + widths[0], y_start)
            pdf.multi_cell(widths[1], 4, row_data[1], 0, 'L', 0, False)
            h_item = pdf.get_y() - y_start
            
            # Remedial Action (Multi-line text in column 3)
            pdf.set_xy(x_start + widths[0] + widths[1], y_start)
            pdf.multi_cell(widths[2], 4, row_data[2], 0, 'L', 0, False)
            h_action = pdf.get_y() - y_start

            row_h = max(max_height, h_item, h_action)
            pdf.set_xy(x_start, y_start) # Reset position for drawing cells

            # Draw cells based on calculated height
            for i, txt in enumerate(row_data):
                align = 'C' if i == 0 or i >= 3 else 'L'
                
                if i in [1, 2]: # Item and Remedial Action
                    x = pdf.get_x()
                    y = pdf.get_y()
                    pdf.multi_cell(widths[i], row_h, txt, 1, 'L', 0, False)
                    pdf.set_xy(x + widths[i], y) # Move cursor right
                else:
                    # Other columns (NO, COLOUR, SIZE, QTY)
                    pdf.cell(widths[i], row_h, txt, 1, 0, align, 0)
            
            pdf.ln(row_h)
        
        # --- 3. Return the PDF ---
        pdf_output = pdf.output(dest='S')
        pdf_file = BytesIO(pdf_output)

        customer_name = data.get('customerName', 'Customer').replace(' ', '_')
        date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        filename = f"Remedial_Checklist_{customer_name}_{date_str}.pdf"
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.exception(f"PDF generation failed on server (fpdf2): {e}")
        return jsonify({"error": f"Server failed to generate PDF: {str(e)}"}), 500

# ========================================================================
# 🛠️ ROUTE: CHECKLIST SAVE (Internal Staff Forms)
# ========================================================================
@form_bp.route('/checklists/save', methods=['POST', 'OPTIONS'])
def save_checklist():
    """
    Handles POST requests to save internal staff checklists (e.g., Remedial Action Checklist).
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        data = request.get_json(silent=True) or {}
        checklist_type = data.get('checklistType', 'unknown')
        customer_id = data.get('customerId')
        customer_name = data.get('customerName', 'N/A')

        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found, cannot save checklist'}), 404
            
        customer_form_data = CustomerFormData(
            customer_id=customer_id,
            form_data=json.dumps(data), 
            token_used='', 
            submitted_at=datetime.utcnow()
        )
        
        db.session.add(customer_form_data)
        db.session.commit()
        
        current_app.logger.info(f"Staff checklist '{checklist_type}' saved for customer {customer_id} ({customer_name}). ID: {customer_form_data.id}")

        return jsonify({
            "message": f"{checklist_type.title()} Checklist saved successfully!",
            "form_submission_id": customer_form_data.id
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error saving internal checklist: {e}")
        return jsonify({"error": f"Failed to save checklist: {str(e)}"}), 500

@form_bp.route('/customers/<customer_id>/generate-form-link', methods=['POST', 'OPTIONS'])
def generate_customer_form_link(customer_id):
    """Generate form link for specific customer"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        # Verify customer exists
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({
                'success': False,
                'error': 'Customer not found'
            }), 404

        data = request.get_json(silent=True) or {}
        form_type = data.get('formType', 'bedroom')  # bedroom or kitchen

        token = generate_secure_token()
        expiration = datetime.now() + timedelta(hours=24)
        
        # Store token with customer association
        form_tokens[token] = {
            'customer_id': customer_id,
            'form_type': form_type,
            'created_at': datetime.now(),
            'expires_at': expiration,
            'used': False
        }
        
        current_app.logger.debug(f"Generated token {token} for customer {customer_id}, expires {expiration}")

        return jsonify({
            'success': True,
            'token': token,
            'form_type': form_type,
            'expires_at': expiration.isoformat(),
            'message': f'{form_type.title()} form link generated successfully'
        }), 200

    except Exception as e:
        current_app.logger.exception(f"Failed to generate form link for customer {customer_id}")
        return jsonify({
            'success': False,
            'error': f'Failed to generate form link: {str(e)}'
        }), 500

@form_bp.route('/validate-form-token/<token>', methods=['GET', 'OPTIONS'])
def validate_form_token(token):
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        current_app.logger.debug(f"Validating token: {token}")
        if token not in form_tokens:
            return jsonify({'valid': False, 'error': 'Invalid token'}), 404

        token_data = form_tokens[token]

        if datetime.now() > token_data['expires_at']:
            del form_tokens[token]
            return jsonify({'valid': False, 'error': 'Token has expired'}), 410

        if token_data['used']:
            return jsonify({'valid': False, 'error': 'Token has already been used'}), 410

        return jsonify({
            'valid': True, 
            'expires_at': token_data['expires_at'].isoformat(),
            'customer_id': token_data.get('customer_id'),
            'form_type': token_data.get('form_type')
        }), 200

    except Exception as e:
        current_app.logger.exception("Token validation failed")
        return jsonify({'valid': False, 'error': f'Validation failed: {str(e)}'}), 500

@form_bp.route('/submit-customer-form', methods=['POST', 'OPTIONS'])
def submit_customer_form():
    """Submit form - creates only ONE submission record"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        data = request.get_json(silent=True) or {}
        token = data.get('token')
        form_data = data.get('formData', {})

        if not form_data:
            return jsonify({'success': False, 'error': 'Missing form data'}), 400

        customer_id = None
        
        # Try token-based submission first (for existing customers)
        if token:
            current_app.logger.debug(f"Processing token-based submission with token: {token}")
            
            if token not in form_tokens:
                return jsonify({'success': False, 'error': 'Invalid or expired token'}), 400

            token_data = form_tokens[token]
            
            # Check expiration
            if datetime.now() > token_data['expires_at']:
                del form_tokens[token]
                return jsonify({'success': False, 'error': 'Token has expired'}), 410
                
            # Check if already used
            if token_data['used']:
                return jsonify({'success': False, 'error': 'Token has already been used'}), 410

            customer_id = token_data.get('customer_id')
            
            # Verify customer exists
            if customer_id:
                customer = Customer.query.get(customer_id)
                if not customer:
                    return jsonify({'success': False, 'error': 'Associated customer not found'}), 404
                
                # Mark token as used
                form_tokens[token]['used'] = True
                current_app.logger.info(f"Token {token} marked as used for customer {customer_id}")
        
        # If no valid token or customer_id from token, try alternative methods
        if not customer_id:
            # Check if customer_id is provided directly in form data or URL params
            customer_id = form_data.get('customer_id') or request.args.get('customerId')
            
            if customer_id:
                # Verify this customer exists
                customer = Customer.query.get(customer_id)
                if not customer:
                    return jsonify({'success': False, 'error': 'Specified customer not found'}), 404
            else:
                # Fallback: create new customer from form data (legacy behavior)
                customer_name = (form_data.get('customer_name') or '').strip()
                customer_address = (form_data.get('customer_address') or '').strip()
                
                if not customer_name or not customer_address:
                    return jsonify({
                        'success': False, 
                        'error': 'Customer name and address are required for new customer creation'
                    }), 400
                
                customer = Customer(
                    name=customer_name,
                    phone=(form_data.get('customer_phone') or '').strip(),
                    address=customer_address,
                    status='New Lead',
                    created_by='Form Submission'
                )
                db.session.add(customer)
                db.session.flush()  # Get the ID without committing
                customer_id = customer.id
                current_app.logger.info(f"Created new customer {customer_id} from form submission")

        # Create ONLY ONE form submission record
        try:
            customer_form_data = CustomerFormData(
                customer_id=customer_id,
                form_data=json.dumps(form_data),
                token_used=token or '',
                submitted_at=datetime.utcnow()
            )
            db.session.add(customer_form_data)
            db.session.commit()
            
            # Get customer name for response
            final_customer = Customer.query.get(customer_id)
            customer_name = final_customer.name if final_customer else 'Customer'
            
            current_app.logger.info(f"Single form submission created for customer {customer_id}")

            return jsonify({
                'success': True, 
                'customer_id': customer_id,
                'form_submission_id': customer_form_data.id,
                'message': f'Form submitted successfully for {customer_name}'
            }), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Database error during form submission for customer {customer_id}")
            raise e

    except Exception as e:
        current_app.logger.exception("Form submission failed")
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Form submission failed: {str(e)}'}), 500

# Legacy endpoint for backward compatibility
@form_bp.route('/generate-form-link', methods=['POST', 'OPTIONS'])
def generate_form_link():
    """Legacy endpoint - generates token not tied to specific customer"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        token = generate_secure_token()
        expiration = datetime.now() + timedelta(hours=24)
        form_tokens[token] = {
            'created_at': datetime.now(),
            'expires_at': expiration,
            'used': False
        }
        current_app.logger.debug(f"Generated legacy token {token} expires {expiration}")

        return jsonify({
            'success': True,
            'token': token,
            'expires_at': expiration.isoformat(),
            'message': 'Form link generated successfully'
        }), 200

    except Exception as e:
        current_app.logger.exception("Failed to generate form link")
        return jsonify({
            'success': False,
            'error': f'Failed to generate form link: {str(e)}'
        }), 500

@form_bp.route('/cleanup-expired-tokens', methods=['POST', 'OPTIONS'])
def cleanup_expired_tokens():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        current_time = datetime.now()
        expired_tokens = [t for t, d in form_tokens.items() if current_time > d['expires_at']]
        for t in expired_tokens:
            del form_tokens[t]
        return jsonify({
            'success': True, 
            'cleaned_tokens': len(expired_tokens), 
            'remaining_tokens': len(form_tokens)
        }), 200
    except Exception as e:
        current_app.logger.exception("Cleanup failed")
        return jsonify({'success': False, 'error': f'Cleanup failed: {str(e)}'}), 500

# ========================================================================
# 🗑️ ROUTE: DELETE FORM SUBMISSION
# ========================================================================
@form_bp.route('/form-submissions/<int:submission_id>', methods=['DELETE', 'OPTIONS'])
def delete_form_submission(submission_id):
    """Delete a form submission by ID"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        submission = CustomerFormData.query.get(submission_id)
        if not submission:
            current_app.logger.warning(f"Form submission {submission_id} not found")
            return jsonify({'error': 'Form submission not found'}), 404
        
        customer_id = submission.customer_id
        
        db.session.delete(submission)
        db.session.commit()
        
        current_app.logger.info(f"Form submission {submission_id} deleted successfully for customer {customer_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Form submission deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting form submission {submission_id}: {e}")
        return jsonify({'error': f'Failed to delete form submission: {str(e)}'}), 500