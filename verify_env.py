# verify_env.py
import os
from pathlib import Path
import json

def verify_environment():
    print("\nVerifying Environment Setup")
    print("=" * 50)
    
    # Check directory structure
    root_dir = Path(__file__).resolve().parent
    required_dirs = ["app", "secrets", "app/static"]
    
    print("\nDirectory Structure:")
    for dir_path in required_dirs:
        path = root_dir / dir_path
        exists = path.exists()
        print(f"{'✅' if exists else '❌'} {dir_path}: {'Found' if exists else 'Missing'}")
    
    # Check .env file
    env_file = root_dir / ".env"
    print("\n.env File:")
    if env_file.exists():
        print("✅ .env file found")
        print("\nEnvironment Variables:")
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key = line.split('=')[0]
                    print(f"✅ {key}: Set")
    else:
        print("❌ .env file missing")
    
    # Check service account key
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print("\nService Account Credentials:")
    if creds_path:
        creds_file = Path(creds_path)
        if creds_file.exists():
            print(f"✅ Credentials file found: {creds_file}")
            print(f"✅ File size: {creds_file.stat().st_size} bytes")
            
            # Verify JSON format
            try:
                with open(creds_file) as f:
                    creds_data = json.load(f)
                    print(f"✅ Valid JSON format")
                    print(f"✅ Project ID: {creds_data.get('project_id')}")
                    print(f"✅ Client email: {creds_data.get('client_email')}")
            except Exception as e:
                print(f"❌ Error reading credentials file: {str(e)}")
        else:
            print(f"❌ Credentials file not found at: {creds_path}")
    else:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not set")
    
    # Check environment variables
    required_vars = [
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "ROTATION_PERIOD_DAYS",
        "DEV_MODE"
    ]
    
    print("\nRequired Environment Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")

if __name__ == "__main__":
    verify_environment()