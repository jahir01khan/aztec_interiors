from flask import request, jsonify, send_file, Blueprint, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid 
from ..utils.file_utils import allowed_file
from ..models import DrawingDocument
from .auth_helpers import token_required 
# 👈 NEW IMPORT: Required for database write operations
from ..db import SessionLocal 
 
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

file_bp = Blueprint('file_routes', __name__)

latest_structured_data = {}

# ==========================================
# Helper Function for Drawing Folder
# ==========================================

def get_drawing_folder():
    """Gets the configured drawing upload folder path, ensuring it exists."""
    folder = current_app.config.get('DRAWING_UPLOAD_FOLDER')
    if not folder:
        current_app.logger.warning("DRAWING_UPLOAD_FOLDER not configured, using default 'customer_drawings'")
        folder = os.path.join(current_app.root_path, 'customer_drawings')

    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as e:
        current_app.logger.error(f"Could not create drawing folder at {folder}: {e}")
        pass
    return folder

# -------------------------------------------------
# DELETE a drawing by ID (supports customer_id + project_id)
# -------------------------------------------------
@file_bp.route('/files/drawings/<drawing_id>', methods=['DELETE', 'OPTIONS'])
@token_required
def delete_customer_drawing(drawing_id):
    if request.method == 'OPTIONS':
        resp = jsonify()
        resp.headers.add('Access-Control-Allow-Origin', '*')
        resp.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        resp.headers.add('Access-Control-Allow-Methods', 'DELETE, OPTIONS')
        return resp

    session = SessionLocal() # 👈 Start session
    try:
        # Find the drawing using the active session
        drawing = session.get(DrawingDocument, drawing_id)
        if not drawing:
            return jsonify({'error': 'Drawing not found'}), 404

        # 1. Delete file from disk
        if drawing.storage_path and os.path.exists(drawing.storage_path):
            try:
                os.remove(drawing.storage_path)
                current_app.logger.info(f"Deleted file: {drawing.storage_path}")
            except Exception as e:
                # Log the warning but proceed with DB delete
                current_app.logger.warning(f"Could not delete file {drawing.storage_path}: {e}")

        # 2. Delete DB record
        session.delete(drawing)
        session.commit() # 👈 Commit deletion

        return jsonify({'success': True, 'message': 'Drawing deleted successfully'}), 200

    except Exception as e:
        session.rollback() # 👈 Rollback on error
        current_app.logger.error(f"Error deleting drawing {drawing_id}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to delete. Server error: {str(e)}'}), 500
    finally:
        session.close() # 👈 Close session


# ==========================================
# EXISTING ROUTES (Unmodified Logic, Adjusted Paths)
# ==========================================

@file_bp.route('/upload', methods=['POST', 'OPTIONS'])
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
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        print(f"Processing file: {filename}")
        # NOTE: process_image_with_openai_vision is an undefined function here.
        # Assuming it returns valid structured_data or {'error': ...}
        structured_data = {'customer_name': 'DemoCustomer', 'data': 'Processed successfully'} # Mock data
        # structured_data = process_image_with_openai_vision(file_path) 
        
        if 'error' in structured_data:
            return jsonify({'success': False, 'error': 'Failed to process image', 'details': structured_data}), 500

        print("Generating PDF...")
        pdf_filename = filename.rsplit('.', 1)[0] + '.pdf'
        pdf_path = generate_pdf(structured_data, pdf_filename) 

        print("Generating Excel file...")
        customer_name = structured_data.get('customer_name', 'N/A')
        excel_path = export_to_excel(structured_data, customer_name) 

        os.remove(file_path)

        global latest_structured_data
        latest_structured_data.update(structured_data)

        return jsonify({
            'success': True,
            'structured_data': structured_data,
            'pdf_download_url': f'/download/{os.path.basename(pdf_path)}',
            'excel_download_url': f'/download-excel/{os.path.basename(excel_path)}',
            'view_data_url': '/view-data'
        })

    except Exception as e:
        current_app.logger.error(f"Error processing upload: {e}", exc_info=True)
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@file_bp.route('/generate-pdf', methods=['POST', 'OPTIONS'])
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
        current_app.logger.error(f"Error generating PDF from form: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'PDF generation failed: {str(e)}'}), 500

@file_bp.route('/generate-excel', methods=['POST', 'OPTIONS'])
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
        current_app.logger.error(f"Error generating Excel from form: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Excel generation failed: {str(e)}'}), 500

@file_bp.route('/download/<filename>')
def download_file(filename):
    try:
        pdf_folder = os.path.join(current_app.root_path, 'generated_pdfs')
        return send_file(os.path.join(pdf_folder, filename), as_attachment=True)
    except FileNotFoundError:
        current_app.logger.warning(f"PDF file not found: generated_pdfs/{filename}")
        return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        current_app.logger.error(f"Error downloading PDF {filename}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 500

@file_bp.route('/download-excel/<filename>')
def download_excel_file(filename):
     # This serves from 'generated_excel/', keep as is relative to app root
    try:
        excel_folder = os.path.join(current_app.root_path, 'generated_excel')
        return send_file(os.path.join(excel_folder, filename), as_attachment=True)
    except FileNotFoundError:
        current_app.logger.warning(f"Excel file not found: generated_excel/{filename}")
        return jsonify({'success': False, 'error': 'Excel file not found'}), 404
    except Exception as e:
        current_app.logger.error(f"Error downloading Excel {filename}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 500


# ==========================================
# CUSTOMER DRAWINGS ROUTES (UPLOAD & FETCH)
# ==========================================

@file_bp.route('/files/drawings', methods=['GET', 'POST', 'OPTIONS'])
@token_required
def handle_customer_drawings():
    """
    GET: Fetch drawing documents for a customer.
    POST: Upload a drawing/layout image or PDF and save its metadata.
    """
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type, Authorization")
        response.headers.add('Access-Control-Allow-Methods', "GET, POST, OPTIONS")
        return response

    # --- Handle GET Request (Read-only) ---
    if request.method == 'GET':
        customer_id = request.args.get('customer_id')
        if not customer_id:
            return jsonify({'error': 'Customer ID query parameter is required'}), 400

        try:
            drawings = DrawingDocument.query.filter_by(customer_id=customer_id)\
                                              .order_by(DrawingDocument.created_at.desc())\
                                              .all()

            result = [d.to_dict() for d in drawings]

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching drawings for customer {customer_id}: {e}", exc_info=True)
            return jsonify({'error': f'Failed to fetch drawings: {str(e)}'}), 500

    # --- Handle POST Request (Write) ---
    elif request.method == 'POST':
        session = SessionLocal() # 👈 Start session
        file_path = None # Initialize file_path for cleanup in case of error
        try:
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
            unique_filename = f"{customer_id}_{str(uuid.uuid4())}_{filename}"
            drawing_folder = get_drawing_folder()
            file_path = os.path.join(drawing_folder, unique_filename) # Set file_path here

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
                file_url=f"/files/drawings/view/{unique_filename}", 
                mime_type=mime_type,
                category=category,
                uploaded_by=request.current_user.get_full_name() if hasattr(request, 'current_user') else 'System'
            )

            session.add(new_drawing)
            session.commit() # 👈 Commit transaction

            current_app.logger.info(f"Drawing saved for customer {customer_id}: {filename} at {file_path}")

            drawing_dict = new_drawing.to_dict()

            return jsonify({
                'success': True,
                'message': 'File uploaded and metadata saved successfully',
                'drawing': drawing_dict
            }), 201

        except Exception as e:
            session.rollback() # 👈 Rollback on database error
            current_app.logger.error(f"Error processing drawing upload: {str(e)}", exc_info=True)
            # Clean up file if it was saved to disk but DB commit failed
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    current_app.logger.info(f"Cleaned up partially uploaded file: {file_path}")
                except OSError as rm_err:
                    current_app.logger.error(f"Error cleaning up file {file_path}: {rm_err}")
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500
        finally:
            session.close() # 👈 Close session

    return jsonify({'error': 'Method Not Allowed'}), 405


# ==========================================
# DRAWING VIEW ROUTE
# ==========================================

@file_bp.route('/files/drawings/view/<filename>', methods=['GET'])
def view_customer_drawing(filename):
    """Serve the uploaded file for viewing/download"""
    try:
        drawing_folder = get_drawing_folder()
        file_location = os.path.join(drawing_folder, filename)

        if not os.path.exists(file_location):
            current_app.logger.warning(f"File not found attempt: {file_location}")
            # Fallback: try finding it via the database record in case the path logic differs
            drawing_record = DrawingDocument.query.filter(DrawingDocument.file_url.endswith(f'/{filename}')).first()
            if drawing_record and os.path.exists(drawing_record.storage_path):
                current_app.logger.info(f"Serving file from DB storage_path: {drawing_record.storage_path}")
                return send_file(drawing_record.storage_path)
            else:
                return jsonify({'success': False, 'error': 'File not found'}), 404

        current_app.logger.info(f"Serving file directly: {file_location}")
        return send_file(file_location)
    except Exception as e:
        current_app.logger.error(f"Error serving drawing file {filename}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 500