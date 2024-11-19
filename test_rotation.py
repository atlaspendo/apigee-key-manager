# test_rotation.py
import asyncio
from datetime import datetime
import json
from google.cloud import secretmanager_v1

async def test_rotation():
    try:
        # Import after setup
        from app.main import key_manager, Config, secret_manager
        
        app_name = "test-app"
        print(f"\nTesting rotation for app: {app_name}")
        
        # Get current secret
        print("\nCurrent secret details:")
        current_secret = await secret_manager.get_secret(app_name)
        print(f"Key: {current_secret['credentials']['key']}")
        print(f"Last Rotated: {current_secret['metadata']['last_rotated']}")
        
        # Rotate secret
        print("\nRotating secret...")
        result = await key_manager.rotate_secret(app_name)
        print("Rotation completed!")
        
        # Verify new secret
        print("\nNew secret details:")
        new_secret = await secret_manager.get_secret(app_name)
        print(f"New Key: {new_secret['credentials']['key']}")
        print(f"New Last Rotated: {new_secret['metadata']['last_rotated']}")
        
        # Verify keys are different
        keys_changed = current_secret['credentials']['key'] != new_secret['credentials']['key']
        print(f"\nKeys were changed: {'✅' if keys_changed else '❌'}")
        
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_rotation())