import os
from flask import Blueprint, request, jsonify, current_app, send_file
from models import db, Customer, CustomerFormData # Assumes models are correct
import secrets
import string
import json
from datetime import datetime, timedelta
from io import BytesIO
from fpdf import FPDF

form_bp = Blueprint("form", __name__)

# In-memory storage for form tokens (for production use Redis/DB)
form_tokens = {}

def generate_secure_token(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# ------------------------------------------------------------------------
# PDF GENERATION HELPERS (Using fpdf2)
# ------------------------------------------------------------------------

class PDF(FPDF):
    def header(self):
        # NOTE: Using a static path is risky. In a production Flask app,
        # you'd use a path relative to the app root, e.g., os.path.join(current_app.root_path, 'static', 'images', 'logo.png')
        logo_path = r"C:\Users\ayaan\Techmynt Solutions\aztec-interior\public\images\logo.png"
        logo_width = 18
        text_margin_x = 3  # Space between logo and text
        
        # Approximate width of the text
        text_block_width = 50 
        
        # Total combined width
        combined_width = logo_width + text_margin_x + text_block_width 
        
        # Calculate X position for centering
        page_width = 210  # A4 width in mm
        x_start_centered = (page_width - combined_width) / 2
        
        y_start = 8 
        logo_height_used = 20
        content_after_header_y = y_start + logo_height_used + 5

        if os.path.exists(logo_path):
            try:
                # Place the logo
                self.image(logo_path, x=x_start_centered, y=y_start, w=logo_width)
                
                # Calculate text starting position
                text_x_start = x_start_centered + logo_width + text_margin_x
                
                # Company Name - use cell instead of multi_cell
                self.set_xy(text_x_start, y_start + 2)  # +2 for slight vertical adjustment
                self.set_font('Arial', 'B', 16)
                self.cell(text_block_width, 7, 'AZTEC INTERIORS', 0, 0, 'L')
                
                # Document Title (will be set dynamically by routes or default to RECEIPT)
                title = getattr(self, 'doc_title', 'DOCUMENT')
                self.set_xy(text_x_start, y_start + 10)  # Position below company name
                self.set_font('Arial', '', 12)
                self.cell(text_block_width, 5, title.upper(), 0, 0, 'L')
                
                # Set cursor for body content
                self.set_y(content_after_header_y)
                
            except Exception as e:
                # Fallback if image fails
                self.set_y(y_start)
                self.set_font('Arial', 'B', 16)
                self.cell(0, 10, 'AZTEC INTERIORS', 0, 1, 'C')
                self.set_font('Arial', '', 12)
                self.cell(0, 5, 'DOCUMENT', 0, 1, 'C')
                self.ln(5)
        else:
            # Fallback if logo not found
            self.set_y(y_start)
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'AZTEC INTERIORS', 0, 1, 'C')
            self.set_font('Arial', '', 12)
            self.cell(0, 5, 'DOCUMENT', 0, 1, 'C')
            self.ln(5)
            
    def footer(self):
        self.set_y(-25)
        self.set_font('Arial', 'B', 8)
        self.cell(0, 5, 'Aztec Interiors (Leicester) Ltd', 0, 1, 'C')
        self.set_font('Arial', '', 8)
        self.cell(0, 4, '127b Barkby Road (Entrance on Lewisher Road), Leicester LE4 9LG', 0, 1, 'C')
        self.cell(0, 4, 'Tel: 0116 2764516 | www.aztecinteriors.co.uk', 0, 1, 'C')
        self.cell(0, 4, 'Registered to England No. 5246691 | VAT Reg No. 846 8818 72', 0, 1, 'C')
        self.set_y(-8)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

# ------------------------------------------------------------------------
# ROUTE: INVOICE PDF DOWNLOAD
# ------------------------------------------------------------------------
@form_bp.route('/invoices/download-pdf', methods=['POST', 'OPTIONS'])
def download_invoice_pdf():
    """Generates a PDF invoice based on data from the frontend."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    try:
        data = request.get_json(silent=True) or {}
        
        if not data:
            return jsonify({'error': 'Missing invoice data.'}), 400

        pdf = PDF('P', 'mm', 'A4')
        pdf.doc_title = 'Invoice'
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Increased margin to prevent footer overlap
        pdf.set_auto_page_break(auto=True, margin=35) 
        
        pdf.set_font('Arial', '', 10)
        
        # Colors for Gray Theme
        HEADER_FILL = (230, 230, 230)
        LINE_COLOR = (0, 0, 0)
        
        col_width = 190 / 2
        line_height = 6
        
        # --- 1. Invoice Number and Dates (Top Right) ---
        pdf.set_x(110)
        pdf.set_fill_color(*HEADER_FILL)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, line_height, 'INVOICE NO:', 1, 0, 'L', 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(40, line_height, data.get('invoiceNumber', 'N/A'), 1, 1, 'R', 0)
        
        pdf.set_x(110)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, line_height, 'DATE:', 1, 0, 'L', 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(40, line_height, data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')), 1, 1, 'R', 0)
        
        pdf.set_x(110)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, line_height, 'DUE DATE:', 1, 0, 'L', 1)
        pdf.set_font('Arial', 'B', 10) # BOLD for due date
        pdf.cell(40, line_height, data.get('dueDate', 'N/A'), 1, 1, 'R', 0)
        pdf.ln(5)
        
        # --- 2. Customer Details (Left) ---
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, line_height, 'BILL TO:', 'T', 1, 'L', 0)
        
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, line_height, data.get('customerName', 'N/A'), 0, 1, 'L', 0)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(col_width, line_height, data.get('customerAddress', 'N/A'), 0, 'L', 0)
        pdf.cell(0, line_height, data.get('customerPhone', 'N/A'), 0, 1, 'L', 0)
        pdf.ln(10)
        
        # --- 3. Line Items Table ---
        header = ['QTY', 'DESCRIPTION', 'UNIT PRICE', 'AMOUNT']
        widths = [15, 105, 35, 35] 
        
        pdf.set_fill_color(*HEADER_FILL)
        pdf.set_font('Arial', 'B', 9)
        
        # Table Header
        for i, h in enumerate(header):
            align = 'C' if i == 0 else ('R' if i >= 2 else 'L')
            pdf.cell(widths[i], 8, h, 1, 0, align, 1)
        pdf.ln()

        # Table Rows
        pdf.set_font('Arial', '', 9)
        
        for item in data.get('items', []):
            description = item.get('description', '')
            amount = item.get('amount', 0)
            
            # 1. Calculate Row Height
            x_start = pdf.get_x()
            y_start = pdf.get_y()
            
            pdf.set_xy(x_start + widths[0], y_start) 
            pdf.multi_cell(widths[1], 5, description, 0, 'L', False, dry_run=True) 
            row_h = pdf.get_y() - y_start
            row_h = max(5, row_h) 
            
            # Reset cursor position
            pdf.set_xy(x_start, y_start) 
            
            # 2. Draw Cells
            
            # QTY
            pdf.cell(widths[0], row_h, '1', 1, 0, 'C', 0)
            
            # DESCRIPTION 
            pdf.multi_cell(widths[1], row_h, description, 1, 'L', 0, False)
            
            # Cursor Repositioning
            pdf.set_xy(x_start + widths[0] + widths[1], y_start)

            # UNIT PRICE 
            pdf.cell(widths[2], row_h, '', 1, 0, 'R', 0)
            
            # AMOUNT
            amount_str = f"£{amount:,.2f}"
            pdf.cell(widths[3], row_h, amount_str, 1, 1, 'R', 0)
        
        pdf.ln(5)

        # --- 4. Totals (Right Aligned) ---
        totals_x_start = 105
        
        pdf.set_font('Arial', '', 10)
        
        # Subtotal
        pdf.set_x(totals_x_start)
        pdf.cell(50, line_height, 'Subtotal:', 0, 0, 'R')
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, line_height, f"£{data.get('subTotal', 0):,.2f}", 0, 1, 'R')
        
        # VAT Rate / Amount
        pdf.set_x(totals_x_start)
        pdf.set_font('Arial', '', 10)
        vat_label = f"VAT ({data.get('vatRate', 0)}%):"
        pdf.cell(50, line_height, vat_label, 0, 0, 'R')
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, line_height, f"£{data.get('vatAmount', 0):,.2f}", 0, 1, 'R')
        
        # Total
        pdf.set_x(totals_x_start)
        pdf.set_fill_color(*HEADER_FILL)
        pdf.set_draw_color(*LINE_COLOR)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(50, 8, 'TOTAL DUE:', 'T', 0, 'R', 1)
        pdf.cell(40, 8, f"£{data.get('totalAmount', 0):,.2f}", 'T', 1, 'R', 1)
        
        pdf.ln(10) # 10mm break after totals
        
        # --- 5. Bank Details (Bottom Left - AGGRESSIVE FIX) ---
        
        # Calculate Y position to avoid footer (297mm height - 35mm margin)
        Y_LIMIT = 297 - 35
        y_safe_start = Y_LIMIT - 30 # Start 30mm above the hard limit
        
        # If content is currently too low, jump to the safe start position.
        if pdf.get_y() > y_safe_start: 
             pdf.set_y(y_safe_start)
        
        # Force a new line and move cursor back to the left margin (10mm)
        # We must use ln() to change Y, and multi_cell below will reset X, but a redundant ln() helps guarantee separation
        pdf.ln(2) 
        
        # 1. Title
        pdf.set_font('Arial', 'B', 10)
        # Use set_xy to explicitly start from the left margin (10mm is default margin)
        pdf.set_xy(10, pdf.get_y()) 
        pdf.multi_cell(col_width, 5, 'Payment by Bank Transfer:', 0, 'L')
        
        # 2. Account Details
        pdf.set_font('Arial', '', 10)
        # Use set_xy to explicitly start from the left margin again
        pdf.set_xy(10, pdf.get_y()) 
        pdf.multi_cell(col_width, 5, 'Acc Name: Aztec Interiors Leicester LTD | Bank: HSBC\nSort Code: 40-28-06 | Acc No: 43820343', 0, 'L')
        
        # 3. Final Reference Line (The problematic line)
        pdf.set_font('Arial', 'I', 9)
        # Use set_xy to explicitly start from the left margin immediately before the call
        pdf.set_xy(10, pdf.get_y()) 
        pdf.multi_cell(0, 5, 'Please use your name and/or road name as reference.', 0, 'L')


        # --- 6. Return the PDF ---
        pdf_output = pdf.output(dest='S')
        pdf_file = BytesIO(pdf_output)

        customer_name = data.get('customerName', 'Customer').replace(' ', '_')
        filename = f"Invoice_{data.get('invoiceNumber', '0000')}_{customer_name}.pdf"
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.exception(f"Invoice PDF generation failed: {e}")
        return jsonify({"error": f"Server failed to generate Invoice PDF: {str(e)}"}), 500

# ------------------------------------------------------------------------
# ROUTE: INVOICE SAVE (NEWLY ADDED)
# ------------------------------------------------------------------------
@form_bp.route('/invoices/save', methods=['POST', 'OPTIONS'])
def save_invoice():
    """
    Saves invoice data as a CustomerFormData entry.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        data = request.get_json(silent=True) or {}
        customer_id = data.get('customerId')
        
        if not customer_id:
            # If the customer ID is missing, but customerName is provided, you might create a new customer.
            # For simplicity, we enforce customerId presence, assuming customer records exist.
            return jsonify({'error': 'Missing customer ID. Cannot save invoice without an associated customer.'}), 400
            
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found, cannot save invoice'}), 404
            
        # Add metadata to the data payload
        data['form_type'] = f"invoice_{data.get('invoiceNumber', 'general')}"
        data['is_invoice'] = True

        customer_form_data = CustomerFormData(
            customer_id=customer_id,
            form_data=json.dumps(data),
            token_used=f"INVOICE-{data.get('invoiceNumber', 'N/A')}-{customer_id}-{datetime.utcnow().timestamp()}",
            submitted_at=datetime.utcnow()
        )
        
        db.session.add(customer_form_data)
        db.session.commit()
        
        current_app.logger.info(f"Invoice saved for customer {customer_id} (Number: {data.get('invoiceNumber')}). ID: {customer_form_data.id}")

        return jsonify({
            "message": f"Invoice ({data.get('invoiceNumber', 'N/A')}) saved successfully!",
            "form_submission_id": customer_form_data.id
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error saving invoice: {e}")
        return jsonify({"error": f"Failed to save invoice: {str(e)}"}), 500


# ------------------------------------------------------------------------
# ROUTE: RECEIPT PDF DOWNLOAD
# ------------------------------------------------------------------------
@form_bp.route('/receipts/download-pdf', methods=['POST', 'OPTIONS'])
def download_receipt_pdf():
    """Generates a PDF receipt based on form data (Updated with Gray Theme)."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    try:
        data = request.get_json(silent=True) or {}
        
        if not data:
            return jsonify({'error': 'Missing receipt data.'}), 400

        pdf = PDF('P', 'mm', 'A4')
        pdf.doc_title = 'Official Receipt' # Custom property for header
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=30) 
        
        # Colors for Gray Theme
        HEADER_FILL = (230, 230, 230)
        TOTAL_FILL = (200, 200, 200)

        pdf.set_font('Arial', '', 10)

        # --- 1. Customer and Date Details ---
        pdf.set_fill_color(*HEADER_FILL) # Gray fill
        pdf.set_draw_color(0, 0, 0)
        col_width = 190 / 2
        line_height = 7
        
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(col_width, line_height, 'Customer Details', 'T', 0, 'L', 1)
        pdf.cell(col_width, line_height, 'Date', 'T', 1, 'R', 1)
        pdf.set_font('Arial', '', 10)
        
        # Row 1: Name and Date
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(30, line_height, 'Name:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width - 30, line_height, data.get('customerName', 'N/A'), 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width, line_height, data.get('receiptDate', datetime.now().strftime('%d/%m/%Y')), 0, 1, 'R')
        
        # Row 2: Address
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(30, line_height, 'Address:', 0, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(col_width - 30, line_height, data.get('customerAddress', 'N/A'), 0, 'L', 0)
        
        # Row 3: Phone
        y_after_address = pdf.get_y()
        pdf.set_font('Arial', 'B', 10)
        pdf.set_xy(10, y_after_address)
        pdf.cell(30, line_height, 'Phone:', 'B', 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(col_width - 30, line_height, data.get('customerPhone', 'N/A'), 'B', 1, 'L')
        pdf.ln(5)

        # --- 2. Payment Confirmation Message ---
        pdf.set_font('Arial', '', 11)
        pdf.multi_cell(0, 6, f"Confirmation of payment received by BACS for {data.get('paymentDescription', 'your Kitchen/Bedroom Cabinetry')}", 0, 'L')
        pdf.ln(5)

        # --- 3. Paid Amount (Highlight) ---
        pdf.set_fill_color(*TOTAL_FILL) # Darker Gray fill
        pdf.set_font('Arial', 'B', 14)
        
        paid_amount_str = f"£{data.get('paidAmount', 0):,.2f}"

        pdf.cell(col_width, 10, 'Paid:', 1, 0, 'L', 1)
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(col_width, 10, paid_amount_str, 1, 1, 'R', 1)
        pdf.ln(5)

        # --- 4. Summary Details ---
        pdf.set_font('Arial', 'B', 11)
        
        # Paid to Date
        paid_to_date_str = f"£{data.get('totalPaidToDate', 0):,.2f}"
        pdf.cell(col_width, 7, 'Paid to date:', 'T', 0, 'L')
        pdf.set_font('Arial', '', 11)
        pdf.cell(col_width, 7, paid_to_date_str, 'T', 1, 'R')

        # Balance to Pay
        balance_str = f"£{data.get('balanceToPay', 0):,.2f}"
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(col_width, 8, 'Balance to Pay:', 'T', 0, 'L')
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(col_width, 8, balance_str, 'T', 1, 'R')
        pdf.ln(10)
        
        # --- 5. Signature ---
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 5, 'Many Thanks', 0, 1, 'L')
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 12)
        pdf.cell(0, 5, 'Shahida Macci', 0, 1, 'L')

        # --- 6. Return the PDF ---
        pdf_output = pdf.output(dest='S')
        pdf_file = BytesIO(pdf_output)

        customer_name = data.get('customerName', 'Customer').replace(' ', '_')
        date_str = data.get('receiptDate', datetime.now().strftime('%Y-%m-%d'))
        filename = f"Receipt_{data.get('receiptType', 'Payment').title()}_{customer_name}_{date_str}.pdf"
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.exception(f"Receipt PDF generation failed: {e}")
        return jsonify({"error": f"Server failed to generate Receipt PDF: {str(e)}"}), 500


# ------------------------------------------------------------------------
# ROUTE: RECEIPT SAVE (Saves Receipt Data as a Form Submission)
# ------------------------------------------------------------------------
@form_bp.route('/receipts/save', methods=['POST', 'OPTIONS'])
def save_receipt():
    """
    Saves receipt data as a CustomerFormData entry.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        data = request.get_json(silent=True) or {}
        customer_id = data.get('customerId')
        
        if not customer_id:
            return jsonify({'error': 'Missing customer ID'}), 400
            
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found, cannot save receipt'}), 404
            
        # Add a unique identifier/type to the data to distinguish it as a receipt
        data['form_type'] = f"receipt_{data.get('receiptType', 'general')}"
        data['is_receipt'] = True

        customer_form_data = CustomerFormData(
            customer_id=customer_id,
            form_data=json.dumps(data),
            token_used=f"RECEIPT-{data.get('receiptType', '').upper()}-{customer_id}-{datetime.utcnow().timestamp()}",
            submitted_at=datetime.utcnow()
        )
        
        db.session.add(customer_form_data)
        db.session.commit()
        
        current_app.logger.info(f"Receipt saved for customer {customer_id} (Type: {data['receiptType']}). ID: {customer_form_data.id}")

        return jsonify({
            "message": f"Receipt ({data['receiptType'].title()}) saved successfully!",
            "form_submission_id": customer_form_data.id
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error saving receipt: {e}")
        return jsonify({"error": f"Failed to save receipt: {str(e)}"}), 500


# ------------------------------------------------------------------------
# REMAINING ORIGINAL ROUTES (Checklist PDF, Checklist Save, Tokens, Delete)
# ------------------------------------------------------------------------

@form_bp.route('/checklists/download-pdf', methods=['POST', 'OPTIONS'])
def download_checklist_pdf():
    """Generates PDF on the server using fpdf2 (Updated with Gray Theme)."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.get_json(silent=True) or {}
        
        if not data or not data.get('items'):
            return jsonify({'error': 'Missing form data for PDF generation.'}), 400

        pdf = PDF('P', 'mm', 'A4')
        pdf.doc_title = 'Remedial Checklist' # Custom property for header
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font('Arial', '', 10)
        
        # Colors for Gray Theme
        HEADER_FILL_LIGHT = (230, 230, 230)
        HEADER_FILL_DARK = (200, 200, 200)

        # --- 1. Customer and Fitter Details ---
        pdf.set_fill_color(*HEADER_FILL_LIGHT)
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
        # Multi-cell requires moving cursor after
        start_x = pdf.get_x()
        start_y = pdf.get_y()
        pdf.multi_cell(col_width, line_height, data.get('customerAddress', 'N/A'), 'LRT', 'L', 0)
        end_y = pdf.get_y()
        
        # Draw the bottom border for the first cell if the address wraps
        pdf.set_xy(10, end_y - line_height)
        pdf.cell(col_width, line_height, '', 'B', 0, 'L')
        pdf.set_y(end_y) # Reset y position

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
        
        pdf.set_fill_color(*HEADER_FILL_DARK) # Darker Gray for table header
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
            
            # Start multi_cell processing to determine row height
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
                    # Draw border only for multi-cell columns
                    pdf.cell(widths[i], row_h, '', 1, 0, align, 0)
                    pdf.set_xy(x + widths[i], y) # Move cursor right
                else:
                    # Other columns (NO, COLOUR, SIZE, QTY)
                    pdf.cell(widths[i], row_h, txt, 1, 0, align, 0)
            
            # Re-write the multi-line text into the bordered cell
            pdf.set_xy(x_start + widths[0], y_start)
            pdf.multi_cell(widths[1], 4, row_data[1], 0, 'L', 0, False)
            
            pdf.set_xy(x_start + widths[0] + widths[1], y_start)
            pdf.multi_cell(widths[2], 4, row_data[2], 0, 'L', 0, False)

            pdf.set_y(y_start + row_h) # Move cursor for next row
        
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
# ROUTE: CHECKLIST SAVE (Internal Staff Forms)
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
        form_type = data.get('formType', 'bedroom') # bedroom or kitchen

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
                db.session.flush() # Get the ID without committing
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
# ROUTE: DELETE FORM SUBMISSION
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