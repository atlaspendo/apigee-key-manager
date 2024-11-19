import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the app directory to Python path
current_dir = Path(__file__).resolve().parent
app_dir = current_dir / "app"
sys.path.append(str(current_dir))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_add_app():
    try:
        # Import after adding app directory to path
        from app.main import key_manager, Config, secret_manager
        
        # Print configuration
        print("\nConfiguration:")
        print(f"DEV_MODE: {Config.DEV_MODE}")
        print(f"PROJECT_ID: {Config.PROJECT_ID}")
        print(f"CREDENTIALS_PATH: {Config.CREDENTIALS_PATH}")
        print(f"Secret Manager Initialized: {secret_manager is not None}")
        
        # Test credentials file
        if Config.CREDENTIALS_PATH:
            creds_path = Path(Config.CREDENTIALS_PATH)
            print(f"\nCredentials file exists: {creds_path.exists()}")
            if creds_path.exists():
                print(f"Credentials file size: {creds_path.stat().st_size} bytes")
        
        # Create test app
        app_name = "test-app"
        print(f"\nCreating test app: {app_name}")
        
        # Create app
        result = await key_manager.create_app(app_name, 30)
        print("\nApp created successfully!")
        print(f"App Name: {result.app_name}")
        print(f"Consumer Key: {result.consumer_key}")
        print(f"Last Rotated: {result.last_rotated}")
        print(f"Next Rotation: {result.next_rotation}")
        
        # Verify in Secret Manager
        if not Config.DEV_MODE and secret_manager:
            print("\nVerifying in Secret Manager:")
            secret_id = f"apigee-key-{app_name}"
            try:
                secret_data = await secret_manager.get_secret(app_name)
                print("✅ Secret found in Secret Manager!")
                print(f"Secret ID: {secret_id}")
                print(f"Metadata: {secret_data.get('metadata', {})}")
            except Exception as e:
                print(f"❌ Error accessing secret: {str(e)}")
        else:
            print("\nSkipping Secret Manager verification (DEV_MODE or no secret_manager)")
        
        return True
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_add_app())