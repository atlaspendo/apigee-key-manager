# verify_gcp.py
from google.cloud import secretmanager_v1
import os

def verify_gcp_setup():
    try:
        # Check environment variables
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        print("\nChecking GCP Configuration:")
        print(f"Project ID: {project_id}")
        print(f"Credentials Path: {creds_path}")
        
        # Initialize client
        client = secretmanager_v1.SecretManagerServiceClient()
        print("\n✅ Successfully initialized Secret Manager client")
        
        # Try to list secrets
        parent = f"projects/{project_id}"
        secrets = list(client.list_secrets(request={"parent": parent}))
        print(f"✅ Successfully accessed Secret Manager (found {len(secrets)} secrets)")
        
        return True
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    verify_gcp_setup()