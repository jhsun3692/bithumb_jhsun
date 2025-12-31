"""Script to sync coin data from external API to database."""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.database import get_db
from app.services.coin_sync import sync_coins_to_db


def main():
    """Main function to sync coins."""
    print("Starting coin synchronization...")

    db = next(get_db())

    try:
        stats = sync_coins_to_db(db)

        print("\n=== Coin Sync Results ===")
        print(f"✅ Added: {stats['added']} coins")
        print(f"🔄 Updated: {stats['updated']} coins")
        print(f"📊 Total: {stats['total']} coins processed")
        print("\nSync completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()