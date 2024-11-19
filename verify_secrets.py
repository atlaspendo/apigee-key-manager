# verify_secrets.py
from google.cloud import secretmanager_v1
import json
from datetime import datetime
import os

def verify_secrets():
    try:
        # Initialize client
        client = secretmanager_v1.SecretManagerServiceClient()
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        
        print(f"\nChecking secrets in project: {project_id}")
        parent = f"projects/{project_id}"
        
        # List all secrets
        secrets = list(client.list_secrets(request={"parent": parent}))
        apigee_secrets = [s for s in secrets if "apigee-key-" in s.name]
        
        if not apigee_secrets:
            print("No Apigee secrets found!")
            return
            
        print(f"\nFound {len(apigee_secrets)} Apigee secrets:")
        
        for secret in apigee_secrets:
            try:
                secret_id = secret.name.split('/')[-1]
                print(f"\nSecret: {secret_id}")
                print("=" * 50)
                
                # Get latest version
                version_name = f"{secret.name}/versions/latest"
                response = client.access_secret_version(request={"name": version_name})
                secret_data = json.loads(response.payload.data.decode('UTF-8'))
                
                # Display metadata
                metadata = secret_data.get('metadata', {})
                print("\nMetadata:")
                print(f"App Name: {metadata.get('app_name')}")
                print(f"Created At: {metadata.get('created_at')}")
                print(f"Last Rotated: {metadata.get('last_rotated')}")
                print(f"Next Rotation: {metadata.get('next_rotation')}")
                print(f"Rotation Period: {metadata.get('rotation_period_days')} days")
                
                # Display credentials (key only, not secret)
                credentials = secret_data.get('credentials', {})
                print("\nCredentials:")
                print(f"Key: {credentials.get('key')}")
                print("Secret: ********")  # Don't display actual secret
                
                # Calculate days until next rotation
                if metadata.get('next_rotation'):
                    next_rotation = datetime.fromisoformat(metadata['next_rotation'])
                    days_remaining = (next_rotation - datetime.now()).days
                    print(f"\nDays until next rotation: {days_remaining}")
                
                print("\nLabels:")
                for key, value in secret.labels.items():
                    print(f"{key}: {value}")
                
            except Exception as e:
                print(f"Error processing secret {secret.name}: {str(e)}")
                continue
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    verify_secrets()