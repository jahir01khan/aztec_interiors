from db import SessionLocal
from models import DrawingDocument, FormDocument

def cleanup_broken_files():
    """Remove or mark files that are broken"""
    session = SessionLocal()
    
    try:
        # Get all drawings
        all_drawings = session.query(DrawingDocument).all()
        
        # Categorize problems
        local_path_files = []  # Files with /opt/render paths (already lost)
        cloudinary_401_files = []  # Files in Cloudinary but wrong type
        working_files = []  # Files that work
        
        for drawing in all_drawings:
            if not drawing.storage_path:
                local_path_files.append(drawing)
            elif not drawing.storage_path.startswith('http'):
                local_path_files.append(drawing)
            elif '/image/upload/' in drawing.storage_path and '.pdf' in drawing.file_name.lower():
                cloudinary_401_files.append(drawing)
            else:
                working_files.append(drawing)
        
        print(f"File Analysis:")
        print(f"  ✅ Working files: {len(working_files)}")
        print(f"  ❌ Lost files (local paths): {len(local_path_files)}")
        print(f"  ⚠️  PDFs with wrong Cloudinary type: {len(cloudinary_401_files)}")
        print()
        
        if len(local_path_files) == 0 and len(cloudinary_401_files) == 0:
            print("✅ All files are in good shape!")
            return
        
        print("This script will:")
        print(f"  1. DELETE {len(local_path_files)} records with old local paths (files already lost)")
        print(f"  2. DELETE {len(cloudinary_401_files)} PDFs uploaded as wrong type (files exist but can't be accessed)")
        print()
        print("After cleanup, you'll need to re-upload these files fresh.")
        print()
        
        # Show examples
        if local_path_files:
            print("Examples of files with local paths (will be deleted):")
            for f in local_path_files[:3]:
                print(f"  - {f.file_name}")
            print()
        
        if cloudinary_401_files:
            print("Examples of PDFs with wrong type (will be deleted):")
            for f in cloudinary_401_files[:3]:
                print(f"  - {f.file_name}")
            print()
        
        confirm = input("Proceed with cleanup? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("Cleanup cancelled.")
            return
        
        # Delete files with local paths
        deleted_local = 0
        for drawing in local_path_files:
            session.delete(drawing)
            deleted_local += 1
        
        # Delete files with 401 errors
        deleted_401 = 0
        for drawing in cloudinary_401_files:
            session.delete(drawing)
            deleted_401 += 1
        
        # Commit changes
        session.commit()
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Deleted {deleted_local} files with old local paths")
        print(f"   Deleted {deleted_401} PDFs with wrong Cloudinary type")
        print(f"   Kept {len(working_files)} working files")
        print()
        print("Next step: Re-upload the deleted files through the app.")
        print("New uploads will be stored correctly in Cloudinary!")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 70)
    print("FILE CLEANUP SCRIPT")
    print("=" * 70)
    print()
    print("This script removes broken file records from the database.")
    print("The actual files were either already lost or can't be accessed.")
    print()
    cleanup_broken_files()