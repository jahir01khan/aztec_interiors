from flask import request, jsonify, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid # Needed for unique file names

# NOTE: Assuming these imports and configurations exist in your environment:
from config import app, latest_structured_data
from utils.file_utils import allowed_file
from utils.openai_utils import process_image_with_openai_vision
from models import db, DrawingDocument # NEW: Import database and DrawingDocument model
from routes.auth_helpers import token_required # Assuming this helper exists for authorization

try:
    from pdf_generator import generate_pdf
    from excel_exporter import export_to_excel
except ImportError as e:
    print(f"Warning: Could not import PDF/Excel generators: {e}")
    def generate_pdf(data, filename):
        print("PDF generator not available")
        return f"generated_pdfs/{filename}"
    def export_to_excel(data, customer_name):
        print("Excel exporter not available")
        return f"generated_excel/{customer_name}_data.xlsx"

# --- FILE PATH CONFIGURATION (CRITICAL) ---
DRAWING_UPLOAD_FOLDER = os.path.join(app.root_path, 'customer_drawings')
if not os.path.exists(DRAWING_UPLOAD_FOLDER):
    os.makedirs(DRAWING_UPLOAD_FOLDER)
app.config['DRAWING_UPLOAD_FOLDER'] = DRAWING_UPLOAD_FOLDER


# ==========================================
# EXISTING ROUTES (Unmodified)
# ==========================================

@app.route('/upload', methods=['POST', 'OPTIONS'])
def upload_image():
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type")
        response.headers.add('Access-Control-Allow-Methods', "POST,OPTIONS")
        return response
        
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload an image.'}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        print(f"Processing file: {filename}")
        structured_data = process_image_with_openai_vision(file_path)
        if 'error' in structured_data:
            return jsonify({'success': False, 'error': 'Failed to process image', 'details': structured_data}), 500

        print("Generating PDF...")
        pdf_filename = filename.rsplit('.', 1)[0] + '.pdf'
        pdf_path = generate_pdf(structured_data, pdf_filename)

        print("Generating Excel file...")
        customer_name = structured_data.get('customer_name', 'Unknown')
        excel_path = export_to_excel(structured_data, customer_name)

        os.remove(file_path)

        return jsonify({
            'success': True,
            'structured_data': structured_data,
            'pdf_download_url': f'/download/{os.path.basename(pdf_path)}',
            'excel_download_url': f'/download-excel/{os.path.basename(excel_path)}',
            'view_data_url': '/view-data'
        })
        
    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/generate-pdf', methods=['POST', 'OPTIONS'])
def generate_pdf_from_form():
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type")
        response.headers.add('Access-Control-Allow-Methods', "POST,OPTIONS")
        return response
        
    try:
        data = request.json.get('data', {})
        if not data:
            return jsonify({'success': False, 'error': 'No form data provided'}), 400

        customer_name = data.get('customer_name', 'Unknown')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(c for c in customer_name if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
        pdf_filename = f"{clean_name}_{timestamp}.pdf" if customer_name != 'Unknown' else f"bedroom_form_{timestamp}.pdf"

        print("Generating PDF from form data...")
        pdf_path = generate_pdf(data, pdf_filename)

        global latest_structured_data
        latest_structured_data.update(data)

        return jsonify({
            'success': True,
            'pdf_download_url': f'/download/{os.path.basename(pdf_path)}',
            'message': 'PDF generated successfully'
        })
        
    except Exception as e:
        print(f"Error generating PDF from form: {str(e)}")
        return jsonify({'success': False, 'error': f'PDF generation failed: {str(e)}'}), 500

@app.route('/generate-excel', methods=['POST', 'OPTIONS'])
def generate_excel_from_form():
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type")
        response.headers.add('Access-Control-Allow-Methods', "POST,OPTIONS")
        return response
        
    try:
        data = request.json.get('data', {})
        if not data:
            return jsonify({'success': False, 'error': 'No form data provided'}), 400

        print("Generating Excel from form data...")
        customer_name = data.get('customer_name', 'Unknown')
        excel_path = export_to_excel(data, customer_name)

        return jsonify({
            'success': True,
            'excel_download_url': f'/download-excel/{os.path.basename(excel_path)}',
            'message': 'Excel file generated successfully'
        })
        
    except Exception as e:
        print(f"Error generating Excel from form: {str(e)}")
        return jsonify({'success': False, 'error': f'Excel generation failed: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(f'generated_pdfs/{filename}', as_attachment=True)
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 500

@app.route('/download-excel/<filename>')
def download_excel_file(filename):
    try:
        return send_file(f'generated_excel/{filename}', as_attachment=True)
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'Excel file not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 500


# ==========================================
# CUSTOMER DRAWINGS UPLOAD (NEW)
# ==========================================

@app.route('/files/drawings', methods=['POST', 'OPTIONS'])
@token_required
def upload_customer_drawing():
    """Upload a drawing/layout image or PDF and save its metadata"""
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type, Authorization")
        response.headers.add('Access-Control-Allow-Methods', "POST,OPTIONS")
        return response
        
    try:
        # Get metadata from form data
        customer_id = request.form.get('customer_id')
        project_id = request.form.get('project_id')
        
        if not customer_id:
            return jsonify({'error': 'Customer ID is missing from form data'}), 400
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected for upload'}), 400
        
        # Security and Pathing
        filename = secure_filename(file.filename)
        # Create a unique file name to prevent overwrites
        unique_filename = f"{customer_id}_{str(uuid.uuid4())}_{filename}"
        file_path = os.path.join(app.config['DRAWING_UPLOAD_FOLDER'], unique_filename)
        
        # Save the file locally
        file.save(file_path)
        
        # Determine file category/type
        mime_type = file.mimetype
        if 'image' in mime_type:
            category = 'image'
        elif 'pdf' in mime_type:
            category = 'pdf'
        else:
            category = 'other'

        # Create database record
        new_drawing = DrawingDocument(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            project_id=project_id if project_id else None,
            file_name=filename,
            storage_path=file_path,
            file_url=f"/files/drawings/view/{unique_filename}", # Public URL to view/download
            mime_type=mime_type,
            category=category,
            uploaded_by=request.current_user.get_full_name() if hasattr(request, 'current_user') else 'System'
        )

        db.session.add(new_drawing)
        db.session.commit()

        print(f"Drawing saved for customer {customer_id}: {filename}")

        return jsonify({
            'success': True,
            'message': 'File uploaded and metadata saved successfully',
            'drawing': new_drawing.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error processing drawing upload: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/files/drawings/view/<filename>', methods=['GET'])
def view_customer_drawing(filename):
    """Serve the uploaded file for viewing/download"""
    try:
        # Note: You should ideally verify user authentication/access here
        # For simplicity, we assume public access via this unique URL
        return send_file(os.path.join(app.config['DRAWING_UPLOAD_FOLDER'], filename))
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 500
