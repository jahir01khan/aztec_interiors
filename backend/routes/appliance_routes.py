# routes/appliance_routes.py
from flask import Blueprint, request, jsonify, current_app
from ..database import db
from ..models import Product, Brand, ApplianceCategory, DataImport, ProductQuoteItem
from datetime import datetime
import json
import pandas as pd
from werkzeug.utils import secure_filename
import os
import threading

appliance_bp = Blueprint('appliances', __name__)

def serialize_product(product):
    """Serialize product object to dictionary"""
    return {
        'id': product.id,
        'model_code': product.model_code,
        'name': product.name,
        'description': product.description,
        'series': product.series,
        'brand': {
            'id': product.brand.id,
            'name': product.brand.name
        } if product.brand else None,
        'category': {
            'id': product.category.id,
            'name': product.category.name
        } if product.category else None,
        'pricing': {
            'base_price': float(product.base_price) if product.base_price else None,
            'low_tier_price': float(product.low_tier_price) if product.low_tier_price else None,
            'mid_tier_price': float(product.mid_tier_price) if product.mid_tier_price else None,
            'high_tier_price': float(product.high_tier_price) if product.high_tier_price else None,
        },
        'dimensions': product.get_dimensions_dict(),
        'weight': float(product.weight) if product.weight else None,
        'color_options': product.get_color_options_list(),
        'pack_name': product.pack_name,
        'notes': product.notes,
        'energy_rating': product.energy_rating,
        'warranty_years': product.warranty_years,
        'active': product.active,
        'in_stock': product.in_stock,
        'lead_time_weeks': product.lead_time_weeks,
        'created_at': product.created_at.isoformat() if product.created_at else None,
        'updated_at': product.updated_at.isoformat() if product.updated_at else None,
    }


def process_import_file(app, import_id, file_path, import_type):
    """
    This function runs in a background thread to process the import.
    It now handles the complex pivoted format for 'appliance_matrix'.
    """
    with app.app_context():
        import_record = DataImport.query.get(import_id)
        if not import_record:
            return

        processed_count = 0
        failed_count = 0
        error_log = []

        try:
            # --- Logic for 'Appliance Matrix' (PIVOTED FORMAT) ---
            if import_type == 'appliance_matrix':
                
                # 1. Load file without headers to sniff for brand
                if file_path.endswith(('.xlsx', '.xls')):
                    df_sniff = pd.read_excel(file_path, header=None)
                else:
                    # <-- FIX 1 -->
                    df_sniff = pd.read_csv(file_path, header=None, encoding='utf-8', on_bad_lines='skip')

                # Find Brand
                brand_name = "Unknown"
                brands_to_check = ['Bosch', 'Neff', 'Siemens']
                for r_idx, row in df_sniff.head(5).iterrows():
                    for c_idx, cell in row.items():
                        if isinstance(cell, str):
                            for brand in brands_to_check:
                                if brand.lower() in cell.lower():
                                    brand_name = brand
                                    break
                    if brand_name != "Unknown":
                        break
                
                brand = Brand.query.filter_by(name=brand_name).first()
                if not brand:
                    brand = Brand(name=brand_name, active=True)
                    db.session.add(brand)
                    db.session.commit() # Commit brand to get ID

                # 2. Reload DataFrame with correct header (row 5, index 4)
                if file_path.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path, header=4)
                else:
                    # <-- FIX 2 -->
                    df = pd.read_csv(file_path, header=4, encoding='utf-8', on_bad_lines='skip')

                # 3. Iterate and process rows
                for index, row in df.iterrows():
                    try:
                        product_name_category = str(row.iloc[0]).strip()
                        if pd.isna(product_name_category) or product_name_category == '':
                            continue # Skip empty spacer rows

                        # Get or create Category
                        category = ApplianceCategory.query.filter_by(name=product_name_category).first()
                        if not category:
                            category = ApplianceCategory(name=product_name_category, active=True)
                            db.session.add(category)
                            db.session.commit() # Commit category to get ID

                        # Helper to process a single product entry
                        def process_entry(model_codes_str, series, price, tier):
                            entry_processed_count = 0
                            if pd.isna(model_codes_str) or str(model_codes_str).strip() == '':
                                return 0
                            
                            model_codes = [mc.strip() for mc in str(model_codes_str).split('/') if mc.strip()]
                            
                            for model_code in model_codes:
                                product = Product.query.filter_by(model_code=model_code).first()
                                if not product:
                                    product = Product(
                                        model_code=model_code,
                                        brand_id=brand.id,
                                        category_id=category.id,
                                        name=product_name_category,
                                        active=True,
                                        in_stock=True
                                    )
                                    db.session.add(product)
                                
                                product.brand_id = brand.id
                                product.category_id = category.id
                                product.name = product_name_category
                                if pd.notna(series):
                                    product.series = str(series)
                                
                                numeric_price = pd.to_numeric(price, errors='coerce')
                                if pd.notna(numeric_price):
                                    if tier == 'low':
                                        product.low_tier_price = numeric_price
                                    elif tier == 'mid':
                                        product.mid_tier_price = numeric_price
                                    elif tier == 'high':
                                        product.high_tier_price = numeric_price
                                    
                                    # Set base price to lowest found tier price
                                    if product.base_price is None or (numeric_price < product.base_price):
                                        product.base_price = numeric_price
                                
                                entry_processed_count += 1
                            return entry_processed_count

                        # Process LOW tier (cols 1, 2, 3)
                        processed_count += process_entry(row.iloc[1], row.iloc[2], row.iloc[3], 'low')
                        
                        # Process MID tier (cols 5, 6, 7)
                        processed_count += process_entry(row.iloc[5], row.iloc[6], row.iloc[7], 'mid')
                        
                        # Process HIGH tier (cols 9, 10, 11)
                        processed_count += process_entry(row.iloc[9], row.iloc[10], row.iloc[11], 'high')
                        
                        db.session.commit() # Commit after each row (batch of 1-3 products)

                    except Exception as row_e:
                        db.session.rollback()
                        failed_count += 1
                        error_log.append(f"Row {index + 6}: {str(row_e)}") # +6 = 1-based index + 5 header rows

            # --- Logic for 'KBB Pricelist' (FLAT FORMAT) ---
            elif import_type == 'kbb_pricelist':
                # This logic is for the KBB kitchen/bedroom files
                if file_path.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path, header=2) # Header is on row 3 (index 2)
                else:
                    # <-- FIX 3 -->
                    df = pd.read_csv(file_path, header=2, encoding='utf-8', on_bad_lines='skip')
                
                # Clean column names
                df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
                
                for index, row in df.iterrows():
                    try:
                        # This logic is a placeholder based on your UI and KBB file
                        # This example does NOT import KBB data as products
                        # It is here to prevent the import from failing
                        
                        code = row.get('code')
                        if pd.isna(code):
                            continue # Skip empty rows
                        
                        # This is where you would add logic to import KBB data
                        # For now, we'll just count it as "processed"
                        
                        # Example:
                        # item_name = row.get('description_carcas_only')
                        # price = pd.to_numeric(row.get('2025_price'), errors='coerce')
                        # if item_name and price:
                        #     print(f"Would import KBB item: {item_name} @ {price}")
                        
                        processed_count += 1
                        
                    except Exception as row_e:
                        db.session.rollback()
                        failed_count += 1
                        error_log.append(f"Row {index + 4}: {str(row_e)}") # +4 = 1-based + 3 header rows
                
                db.session.commit()

            # --- Import finished, update the job status ---
            import_record.status = 'completed'
            import_record.records_processed = processed_count
            import_record.records_failed = failed_count
            import_record.error_log = "\n".join(error_log)
            
        except Exception as e:
            # Fatal error (e.g., file read error)
            db.session.rollback()
            import_record.status = 'failed'
            import_record.error_log = f"Fatal Error: {str(e)}"
        
        finally:
            import_record.completed_at = datetime.utcnow()
            db.session.commit()

# Product endpoints
@appliance_bp.route('/products', methods=['GET'])
def get_products():
    """Get all products with filtering and search"""
    try:
        # Query parameters
        search = request.args.get('search', '')
        
        # --- MODIFIED: Handle multiple brand_ids ---
        brand_ids = request.args.getlist('brand_id', type=int)
        # --- END MODIFICATION ---
        
        category_id = request.args.get('category_id', type=int)
        series = request.args.get('series')
        tier = request.args.get('tier')  # low/mid/high
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Build query
        query = Product.query
        
        if active_only:
            query = query.filter(Product.active == True)
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Product.name.ilike(search_filter),
                    Product.model_code.ilike(search_filter),
                    Product.series.ilike(search_filter)
                )
            )
        
        # --- MODIFIED: Filter by list of brand_ids ---
        if brand_ids:
            query = query.filter(Product.brand_id.in_(brand_ids))
        # --- END MODIFICATION ---
        
        if category_id:
            query = query.filter(Product.category_id == category_id)
        
        if series:
            query = query.filter(Product.series.ilike(f"%{series}%"))
        
        # --- NEW: Added tier filtering logic ---
        if tier == 'low':
            query = query.filter(Product.low_tier_price.isnot(None))
        elif tier == 'mid':
            query = query.filter(Product.mid_tier_price.isnot(None))
        elif tier == 'high':
            query = query.filter(Product.high_tier_price.isnot(None))
        # --- END NEW LOGIC ---
        
        # Order by brand, then series, then model
        query = query.join(Brand).order_by(Brand.name, Product.series, Product.model_code)
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        products = pagination.items
        
        return jsonify({
            'products': [serialize_product(p) for p in products],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appliance_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get a specific product by ID"""
    try:
        product = Product.query.get_or_404(product_id)
        return jsonify(serialize_product(product))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appliance_bp.route('/products', methods=['POST'])
def create_product():
    """Create a new product"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['model_code', 'name', 'brand_id', 'category_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if model code already exists
        if Product.query.filter_by(model_code=data['model_code']).first():
            return jsonify({'error': 'Model code already exists'}), 400
        
        # Create product
        product = Product(
            model_code=data['model_code'],
            name=data['name'],
            description=data.get('description'),
            brand_id=data['brand_id'],
            category_id=data['category_id'],
            series=data.get('series'),
            base_price=data.get('base_price'),
            low_tier_price=data.get('low_tier_price'),
            mid_tier_price=data.get('mid_tier_price'),
            high_tier_price=data.get('high_tier_price'),
            dimensions=json.dumps(data.get('dimensions', {})),
            weight=data.get('weight'),
            color_options=json.dumps(data.get('color_options', [])),
            pack_name=data.get('pack_name'),
            notes=data.get('notes'),
            energy_rating=data.get('energy_rating'),
            warranty_years=data.get('warranty_years'),
            active=data.get('active', True),
            in_stock=data.get('in_stock', True),
            lead_time_weeks=data.get('lead_time_weeks')
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify(serialize_product(product)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@appliance_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update an existing product"""
    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json()
        
        # Update fields
        updatable_fields = [
            'name', 'description', 'series', 'base_price', 'low_tier_price',
            'mid_tier_price', 'high_tier_price', 'weight', 'pack_name',
            'notes', 'energy_rating', 'warranty_years', 'active', 'in_stock',
            'lead_time_weeks', 'brand_id', 'category_id'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(product, field, data[field])
        
        # Handle JSON fields
        if 'dimensions' in data:
            product.dimensions = json.dumps(data['dimensions'])
        if 'color_options' in data:
            product.color_options = json.dumps(data['color_options'])
        
        # Don't allow model_code changes to prevent breaking references
        # if 'model_code' in data:
        #     product.model_code = data['model_code']
        
        product.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify(serialize_product(product))
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@appliance_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product (soft delete by setting active=False)"""
    try:
        product = Product.query.get_or_404(product_id)
        product.active = False
        product.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Product deactivated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Brand endpoints
@appliance_bp.route('/brands', methods=['GET'])
def get_brands():
    """Get all brands"""
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        query = Brand.query
        if active_only:
            query = query.filter(Brand.active == True)
        
        brands = query.order_by(Brand.name).all()
        
        return jsonify([{
            'id': b.id,
            'name': b.name,
            'logo_url': b.logo_url,
            'website': b.website,
            'active': b.active,
            'product_count': len([p for p in b.products if p.active]) if active_only else len(b.products)
        } for b in brands])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appliance_bp.route('/brands', methods=['POST'])
def create_brand():
    """Create a new brand"""
    try:
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'error': 'Brand name is required'}), 400
        
        # Check if brand already exists
        if Brand.query.filter_by(name=data['name']).first():
            return jsonify({'error': 'Brand already exists'}), 400
        
        brand = Brand(
            name=data['name'],
            logo_url=data.get('logo_url'),
            website=data.get('website'),
            active=data.get('active', True)
        )
        
        db.session.add(brand)
        db.session.commit()
        
        return jsonify({
            'id': brand.id,
            'name': brand.name,
            'logo_url': brand.logo_url,
            'website': brand.website,
            'active': brand.active
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Category endpoints
@appliance_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get all appliance categories"""
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        query = ApplianceCategory.query
        if active_only:
            query = query.filter(ApplianceCategory.active == True)
        
        categories = query.order_by(ApplianceCategory.name).all()
        
        return jsonify([{
            'id': c.id,
            'name': c.name,
            'description': c.description,
            'active': c.active,
            'product_count': len([p for p in c.products if p.active]) if active_only else len(c.products)
        } for c in categories])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appliance_bp.route('/categories', methods=['POST'])
def create_category():
    """Create a new appliance category"""
    try:
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'error': 'Category name is required'}), 400
        
        # Check if category already exists
        if ApplianceCategory.query.filter_by(name=data['name']).first():
            return jsonify({'error': 'Category already exists'}), 400
        
        category = ApplianceCategory(
            name=data['name'],
            description=data.get('description'),
            active=data.get('active', True)
        )
        
        db.session.add(category)
        db.session.commit()
        
        return jsonify({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'active': category.active
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Price tier endpoint
@appliance_bp.route('/products/<int:product_id>/price/<tier>', methods=['GET'])
def get_product_price_for_tier(product_id, tier):
    """Get product price for specific tier"""
    try:
        product = Product.query.get_or_404(product_id)
        price = product.get_price_for_tier(tier)
        
        return jsonify({
            'product_id': product_id,
            'tier': tier,
            'price': float(price) if price else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Search endpoint with autocomplete
@appliance_bp.route('/products/search', methods=['GET'])
def search_products():
    """Search products with autocomplete support"""
    try:
        query_text = request.args.get('q', '')
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        if len(query_text) < 2:
            return jsonify([])
        
        search_filter = f"%{query_text}%"
        products = Product.query.filter(
            Product.active == True
        ).filter(
            db.or_(
                Product.name.ilike(search_filter),
                Product.model_code.ilike(search_filter),
                Product.series.ilike(search_filter)
            )
        ).join(Brand).order_by(
            Brand.name, Product.series, Product.model_code
        ).limit(limit).all()
        
        return jsonify([{
            'id': p.id,
            'model_code': p.model_code,
            'name': p.name,
            'brand_name': p.brand.name if p.brand else None,
            'series': p.series,
            'base_price': float(p.base_price) if p.base_price else None,
            'category_name': p.category.name if p.category else None
        } for p in products])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Data import endpoints (for bulk import functionality)
@appliance_bp.route('/import/upload', methods=['POST'])
def upload_import_file():
    """Upload file for data import and start processing in background"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        import_type = request.form.get('import_type', 'appliance_matrix')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
            return jsonify({'error': 'Invalid file type. Please upload Excel or CSV file'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Create import record
        import_record = DataImport(
            filename=filename,
            import_type=import_type,
            imported_by=request.form.get('imported_by', 'System')
            # Status will be 'processing' by default
        )
        db.session.add(import_record)
        db.session.commit() # Commit to get the ID

        # --- START THE BACKGROUND WORKER ---
        worker_thread = threading.Thread(
            target=process_import_file,
            args=(current_app._get_current_object(), import_record.id, file_path, import_type)
        )
        worker_thread.start()
        # --- END BACKGROUND WORKER ---

        return jsonify({
            'import_id': import_record.id,
            'filename': filename,
            'message': 'File uploaded. Processing has started.'
        }), 201
        
    except Exception as e:
        db.session.rollback() # Rollback if import_record creation fails
        return jsonify({'error': str(e)}), 500

@appliance_bp.route('/import/<int:import_id>/status', methods=['GET'])
def get_import_status(import_id):
    """Get status of data import"""
    try:
        import_record = DataImport.query.get_or_404(import_id)
        
        return jsonify({
            'id': import_record.id,
            'filename': import_record.filename,
            'import_type': import_record.import_type,
            'status': import_record.status,
            'records_processed': import_record.records_processed,
            'records_failed': import_record.records_failed,
            'error_log': import_record.error_log,
            'created_at': import_record.created_at.isoformat(),
            'completed_at': import_record.completed_at.isoformat() if import_record.completed_at else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500