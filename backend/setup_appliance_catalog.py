# setup_appliance_catalog.py - Setup script for appliance catalog
import json
from app import app
from backend.db import SessionLocal, Base, engine
from backend.models import Brand, ApplianceCategory, Product
from sqlalchemy.exc import IntegrityError # Import for robust error handling

def setup_appliance_catalog():
    """Set up the appliance catalog with initial data"""
    # Define data locally for easy modification
    brands_data = [
        {"name": "Bosch", "website": "https://www.bosch-home.co.uk"},
        {"name": "Siemens", "website": "https://www.siemens-home.bsh-group.com"},
        {"name": "NEFF", "website": "https://www.neff-home.com"},
        {"name": "AEG", "website": "https://www.aeg.co.uk"},
        {"name": "Hotpoint", "website": "https://www.hotpoint.co.uk"},
        {"name": "Beko", "website": "https://www.beko.co.uk"},
        {"name": "LG", "website": "https://www.lg.com"},
        {"name": "Samsung", "website": "https://www.samsung.com"},
        {"name": "Miele", "website": "https://www.miele.co.uk"},
        {"name": "Whirlpool", "website": "https://www.whirlpool.co.uk"}
    ]
    
    categories_data = [
        {"name": "Built-in Ovens", "description": "Single and double built-in ovens"},
        {"name": "Hobs", "description": "Gas, electric, and induction hobs"},
        {"name": "Extractors", "description": "Cooker hoods and extractors"},
        {"name": "Microwaves", "description": "Built-in and freestanding microwaves"},
        {"name": "Dishwashers", "description": "Built-in and freestanding dishwashers"},
        {"name": "Refrigeration", "description": "Fridges, freezers, and fridge-freezers"},
        {"name": "Washing Machines", "description": "Freestanding and built-in washing machines"},
        {"name": "Tumble Dryers", "description": "Vented, condenser, and heat pump dryers"},
        {"name": "Range Cookers", "description": "Dual fuel and electric range cookers"},
        {"name": "Wine Coolers", "description": "Built-in and freestanding wine storage"}
    ]
    
    sample_products = [] # Will be populated inside the context
    
    with app.app_context():
        print("Setting up Appliance Catalog...")
        
        # Create tables (uncommented)
        Base.metadata.create_all(bind=engine)

        # Use a single session for all inserts
        with SessionLocal() as session:
            
            # --- 1. Create sample brands ---
            print("Adding Brands...")
            for brand_data in brands_data:
                # Use session.query() instead of Model.query
                if not session.query(Brand).filter_by(name=brand_data["name"]).first():
                    brand = Brand(
                        name=brand_data["name"],
                        website=brand_data["website"],
                        active=True
                    )
                    session.add(brand)
            
            # --- 2. Create sample categories ---
            print("Adding Categories...")
            for category_data in categories_data:
                # Use session.query() instead of Model.query
                if not session.query(ApplianceCategory).filter_by(name=category_data["name"]).first():
                    category = ApplianceCategory(
                        name=category_data["name"],
                        description=category_data["description"],
                        active=True
                    )
                    session.add(category)
            
            # Commit brands and categories now so we can query them by ID for products
            try:
                session.commit()
            except IntegrityError as e:
                session.rollback()
                print(f"Database integrity error during initial commit: {e}")
                return False
                
            
            # --- 3. Prepare Product Data ---
            
            # Get created brands and categories for sample products (using session.query)
            bosch = session.query(Brand).filter_by(name="Bosch").first()
            siemens = session.query(Brand).filter_by(name="Siemens").first()
            neff = session.query(Brand).filter_by(name="NEFF").first()
            
            ovens_category = session.query(ApplianceCategory).filter_by(name="Built-in Ovens").first()
            hobs_category = session.query(ApplianceCategory).filter_by(name="Hobs").first()
            dishwashers_category = session.query(ApplianceCategory).filter_by(name="Dishwashers").first()
            
            # Populate sample_products list using the retrieved IDs
            if bosch and ovens_category:
                sample_products.extend([
                    {
                        "brand_id": bosch.id,
                        "category_id": ovens_category.id,
                        "model_code": "HBA5360S0B",
                        "name": "Serie 6 Built-in Single Oven",
                        "description": "60cm built-in electric single oven with EcoClean Direct cleaning",
                        "series": "Serie 6",
                        "base_price": 649.00,
                        "low_tier_price": 599.00,
                        "mid_tier_price": 649.00,
                        "high_tier_price": 699.00,
                        "dimensions": json.dumps({"width": 59.5, "height": 59.5, "depth": 54.8}),
                        "energy_rating": "A",
                        "warranty_years": 2,
                        "color_options": json.dumps(["Stainless Steel", "Black"])
                    },
                    {
                        "brand_id": bosch.id,
                        "category_id": ovens_category.id,
                        "model_code": "MBA5350S0B",
                        "name": "Serie 6 Built-in Double Oven",
                        "description": "60cm built-in electric double oven with EcoClean Direct",
                        "series": "Serie 6",
                        "base_price": 899.00,
                        "low_tier_price": 849.00,
                        "mid_tier_price": 899.00,
                        "high_tier_price": 949.00,
                        "dimensions": json.dumps({"width": 59.5, "height": 88.8, "depth": 54.8}),
                        "energy_rating": "A",
                        "warranty_years": 2,
                        "color_options": json.dumps(["Stainless Steel"])
                    }
                ])
            
            if siemens and hobs_category:
                sample_products.extend([
                    {
                        "brand_id": siemens.id,
                        "category_id": hobs_category.id,
                        "model_code": "EX675LXC1E",
                        "name": "iQ700 Induction Hob",
                        "description": "70cm induction hob with flexInduction zones",
                        "series": "iQ700",
                        "base_price": 899.00,
                        "low_tier_price": 829.00,
                        "mid_tier_price": 899.00,
                        "high_tier_price": 999.00,
                        "dimensions": json.dumps({"width": 70.2, "height": 5.1, "depth": 52.2}),
                        "energy_rating": "A++",
                        "warranty_years": 2,
                        "color_options": json.dumps(["Black"])
                    }
                ])
            
            if neff and dishwashers_category:
                sample_products.extend([
                    {
                        "brand_id": neff.id,
                        "category_id": dishwashers_category.id,
                        "model_code": "S155HAX27G",
                        "name": "Built-in Dishwasher",
                        "description": "60cm fully integrated dishwasher with TimeLight",
                        "series": "N50",
                        "base_price": 499.00,
                        "low_tier_price": 449.00,
                        "mid_tier_price": 499.00,
                        "high_tier_price": 549.00,
                        "dimensions": json.dumps({"width": 59.8, "height": 81.5, "depth": 55.0}),
                        "energy_rating": "D",
                        "warranty_years": 2,
                        "color_options": json.dumps(["Stainless Steel"])
                    }
                ])
            
            # --- 4. Create sample products ---
            print("Adding Products...")
            for product_data in sample_products:
                # Use session.query() instead of Model.query
                if not session.query(Product).filter_by(model_code=product_data["model_code"]).first():
                    product = Product(**product_data)
                    session.add(product)
            
            # Final commit for products
            try:
                session.commit()
            except IntegrityError as e:
                session.rollback()
                print(f"Database integrity error during product commit: {e}")
                return False

            # --- 5. Print Summary ---
            print("✅ Appliance Catalog setup completed!")
            # Use session.query().count() for accurate counts
            print(f"Created {session.query(Brand).count()} brands")
            print(f"Created {session.query(ApplianceCategory).count()} categories") 
            print(f"Created {session.query(Product).count()} sample products")
            
            return True

if __name__ == '__main__':
    setup_appliance_catalog()