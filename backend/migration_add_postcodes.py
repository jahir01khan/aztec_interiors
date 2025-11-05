# migration_add_postcodes.py (Corrected)

# 1. Corrected Imports: Importing from the same directory
from .models import Customer 
from .db import SessionLocal
import sys
from sqlalchemy.exc import SQLAlchemyError
import re

def extract_postcode_from_address(address):
    """Extract UK postcode from address string"""
    if not address:
        return None
    pattern = r'\b[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}\b'
    match = re.search(pattern, address.upper())
    return match.group(0) if match else None

def fix_postcodes():
    session = SessionLocal()
    try:
        # Get ALL customers to check them
        all_customers = session.query(Customer).all()
        
        print(f"Total customers found: {len(all_customers)}")
        
        updated_count = 0
        no_postcode_count = 0
        
        for customer in all_customers:
            # Check if postcode is NULL or empty
            if not customer.postcode or customer.postcode.strip() == '':
                no_postcode_count += 1
                print(f"\n❌ {customer.name} has no postcode")
                print(f"   Address: {customer.address}")
                
                # Try to extract from address
                extracted = extract_postcode_from_address(customer.address)
                if extracted:
                    customer.postcode = extracted
                    updated_count += 1
                    print(f"   ✅ Extracted: {extracted}")
                else:
                    print(f"   ⚠️ Could not extract postcode")
            else:
                print(f"✓ {customer.name}: {customer.postcode}")
        
        if updated_count > 0:
            print(f"\n--- Committing changes ---")
            session.commit()
            print(f"✅ Updated {updated_count} out of {no_postcode_count} customers with missing postcodes")
        else:
            print(f"\n⚠️ Found {no_postcode_count} customers with missing postcodes but couldn't extract any")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    print("=== Postcode Fix Script ===\n")
    fix_postcodes()