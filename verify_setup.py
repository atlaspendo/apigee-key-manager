# verify_setup.py
import os
from google.cloud import secretmanager_v1
from google.oauth2 import service_account

def verify_setup():
    try:
        # Check if credentials file exists
        creds_path = "./secrets/service-account.json"
        if not os.path.exists(creds_path):
            print("❌ Service account key file not found!")
            return False

        # Try to load credentials
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        print("✅ Service account credentials loaded successfully")

        # Try to initialize Secret Manager client
        client = secretmanager_v1.SecretManagerServiceClient(credentials=credentials)
        print("✅ Secret Manager client initialized successfully")

        # Try to list secrets (tests permissions)
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        parent = f"projects/{project_id}"
        list(client.list_secrets(request={"parent": parent}))
        print("✅ Successfully listed secrets - permissions verified")

        return True

    except Exception as e:
        print(f"❌ Setup verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    verify_setup()