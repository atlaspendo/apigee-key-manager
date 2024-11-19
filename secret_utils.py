# secret_utils.py
from google.cloud import secretmanager_v1
from google.api_core import exceptions
import json
from datetime import datetime
import os

class SecretVerifier:
    def __init__(self):
        self.client = secretmanager_v1.SecretManagerServiceClient()
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
        self.parent = f"projects/{self.project_id}"

    def verify_app_secret(self, app_name: str) -> dict:
        """Verify secret exists and get its details"""
        try:
            secret_id = f"apigee-key-{app_name}"
            secret_path = f"{self.parent}/secrets/{secret_id}/versions/latest"
            
            # Try to access the secret
            response = self.client.access_secret_version(request={"name": secret_path})
            data = json.loads(response.payload.data.decode('UTF-8'))
            
            return {
                "exists": True,
                "key": data.get("credentials", {}).get("key"),
                "last_rotated": data.get("metadata", {}).get("last_rotated"),
                "next_rotation": data.get("metadata", {}).get("next_rotation"),
                "versions": self.get_secret_versions(secret_id)
            }
        except exceptions.NotFound:
            return {"exists": False, "error": "Secret not found"}
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def get_secret_versions(self, secret_id: str) -> list:
        """Get all versions of a secret"""
        try:
            secret_path = f"{self.parent}/secrets/{secret_id}"
            versions = list(self.client.list_secret_versions(request={"parent": secret_path}))
            return [
                {
                    "version": v.name.split('/')[-1],
                    "state": "ENABLED" if v.state == secretmanager_v1.SecretVersion.State.ENABLED else "DISABLED",
                    "create_time": v.create_time.isoformat()
                }
                for v in versions
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def verify_all_apps(self) -> dict:
        """Verify all Apigee key secrets"""
        try:
            secrets = list(self.client.list_secrets(request={"parent": self.parent}))
            results = {}
            
            for secret in secrets:
                if "apigee-key-" in secret.name:
                    app_name = secret.name.split('/')[-1].replace('apigee-key-', '')
                    results[app_name] = self.verify_app_secret(app_name)
                    
            return results
        except Exception as e:
            return {"error": str(e)}

def verify_app(app_name: str):
    """Utility function to verify a single app"""
    verifier = SecretVerifier()
    result = verifier.verify_app_secret(app_name)
    
    if result["exists"]:
        print(f"\nApp: {app_name}")
        print(f"Key: {result['key']}")
        print(f"Last rotated: {result['last_rotated']}")
        print(f"Next rotation: {result['next_rotation']}")
        print("\nSecret versions:")
        for version in result["versions"]:
            print(f"  Version {version['version']}: {version['state']} ({version['create_time']})")
    else:
        print(f"\nError: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    # You can use this as a command-line tool
    import sys
    if len(sys.argv) > 1:
        verify_app(sys.argv[1])
    else:
        verifier = SecretVerifier()
        results = verifier.verify_all_apps()
        print(json.dumps(results, indent=2))