from db import SessionLocal
from models import DrawingDocument, FormDocument
import re

def extract_filename_from_url(url):
    """Extract the unique filename from a Cloudinary URL"""
    if not url:
        return None
    
    # Cloudinary URL format: https://res.cloudinary.com/.../folder/customer-id/filename.ext
    # We want to extract the full unique filename
    parts = url.split('/')
    if len(parts) >= 2:
        # Get the last part (filename with extension)
        filename = parts[-1]
        return filename
    
    return None

def migrate_file_urls():
    """Update all file records to use backend URLs instead of direct Cloudinary URLs"""
    session = SessionLocal()
    
    try:
        # Find all drawings with Cloudinary URLs in file_url field
        drawings = session.query(DrawingDocument).filter(
            DrawingDocument.file_url.like('%cloudinary%')
        ).all()
        
        # Find all forms with Cloudinary URLs in file_url field
        forms = session.query(FormDocument).filter(
            FormDocument.file_url.like('%cloudinary%')
        ).all()
        
        print(f"Found {len(drawings)} drawings to migrate")
        print(f"Found {len(forms)} form documents to migrate")
        print()
        
        if len(drawings) == 0 and len(forms) == 0:
            print("✅ No files need migration - all URLs are already correct!")
            return
        
        print("This script will:")
        print("  1. Move Cloudinary URLs from file_url → storage_path")
        print("  2. Set file_url to backend view URL (e.g., /files/drawings/view/filename.pdf)")
        print("  3. Enable PDFs to open inline in browser")
        print()
        
        # Show examples
        if drawings:
            example = drawings[0]
            filename = extract_filename_from_url(example.file_url)
            print(f"Example drawing:")
            print(f"  Current file_url: {example.file_url[:80]}...")
            print(f"  New file_url: /files/drawings/view/{filename}")
            print(f"  New storage_path: {example.file_url[:80]}...")
            print()
        
        confirm = input("Proceed with migration? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("Migration cancelled.")
            return
        
        # Migrate drawings
        updated_drawings = 0
        for drawing in drawings:
            # Extract filename from the Cloudinary URL
            filename = extract_filename_from_url(drawing.file_url)
            
            if not filename:
                print(f"⚠️  Warning: Could not extract filename from {drawing.id}")
                continue
            
            # Move Cloudinary URL to storage_path
            old_file_url = drawing.file_url
            drawing.storage_path = old_file_url
            
            # Set file_url to backend view URL
            drawing.file_url = f"/files/drawings/view/{filename}"
            
            updated_drawings += 1
        
        # Migrate forms
        updated_forms = 0
        for form in forms:
            # Extract filename from the Cloudinary URL
            filename = extract_filename_from_url(form.file_url)
            
            if not filename:
                print(f"⚠️  Warning: Could not extract filename from {form.id}")
                continue
            
            # Move Cloudinary URL to storage_path
            old_file_url = form.file_url
            form.storage_path = old_file_url
            
            # Set file_url to backend view URL
            form.file_url = f"/files/forms/view/{filename}"
            
            updated_forms += 1
        
        # Commit all changes
        session.commit()
        
        print(f"\n✅ Migration complete!")
        print(f"   Updated {updated_drawings} drawings")
        print(f"   Updated {updated_forms} form documents")
        print()
        print("All PDFs will now open inline in the browser!")
        print()
        print("Note: Images will also go through the backend now, but will")
        print("      be redirected to Cloudinary (no performance impact).")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        print("\nMigration rolled back - no changes were made.")
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 70)
    print("FILE URL MIGRATION SCRIPT")
    print("=" * 70)
    print()
    print("This script updates file URLs to enable PDFs to open inline.")
    print()
    migrate_file_urls()