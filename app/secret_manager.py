# app/secret_manager.py
from google.cloud import secretmanager_v1
from google.api_core import exceptions
from datetime import datetime, timedelta
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class SecretManagerClient:
    def __init__(self, project_id: str):
        """Initialize Secret Manager client with existing credentials"""
        try:
            self.project_id = project_id
            self.client = secretmanager_v1.SecretManagerServiceClient()
            self.parent = f"projects/{project_id}"
            logger.info(f"Initialized Secret Manager for project: {project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Secret Manager: {str(e)}")
            raise

    async def store_api_key(self, app_name: str, credentials: Dict, rotation_period_days: int) -> Dict:
        """Store API key and secret in Secret Manager"""
        try:
            # Prepare secret data
            secret_data = {
                "credentials": credentials,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_rotated": datetime.now().isoformat(),
                    "next_rotation": (datetime.now() + timedelta(days=rotation_period_days)).isoformat(),
                    "rotation_period_days": rotation_period_days
                }
            }

            # Check if secret exists
            secret_id = f"apigee-key-{app_name}"
            secret_path = f"{self.parent}/secrets/{secret_id}"

            try:
                # Try to access existing secret
                self.client.get_secret(request={"name": secret_path})
                logger.info(f"Secret already exists for app: {app_name}")
            except exceptions.NotFound:
                # Create new secret if it doesn't exist
                self.client.create_secret(
                    request={
                        "parent": self.parent,
                        "secret_id": secret_id,
                        "secret": {
                            "replication": {"automatic": {}},
                            "labels": {
                                "app": app_name,
                                "created_by": "apigee-key-manager",
                                "created_at": datetime.now().strftime("%Y%m%d")
                            }
                        }
                    }
                )
                logger.info(f"Created new secret for app: {app_name}")

            # Add new version with the credentials
            secret_value = json.dumps(secret_data).encode("UTF-8")
            version = self.client.add_secret_version(
                request={
                    "parent": secret_path,
                    "payload": {"data": secret_value}
                }
            )
            logger.info(f"Added new version for app: {app_name}")

            return secret_data

        except Exception as e:
            logger.error(f"Error storing API key for {app_name}: {str(e)}")
            raise

    async def get_api_key(self, app_name: str) -> Optional[Dict]:
        """Get API key and secret from Secret Manager"""
        try:
            secret_id = f"apigee-key-{app_name}"
            name = f"{self.parent}/secrets/{secret_id}/versions/latest"
            
            response = self.client.access_secret_version(request={"name": name})
            return json.loads(response.payload.data.decode("UTF-8"))

        except exceptions.NotFound:
            logger.warning(f"No secret found for app: {app_name}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving API key for {app_name}: {str(e)}")
            raise

    async def list_api_keys(self) -> list:
        """List all API keys in Secret Manager"""
        try:
            secrets = []
            request = {"parent": self.parent, "filter": "labels.created_by=apigee-key-manager"}
            
            # List all secrets with our label
            for secret in self.client.list_secrets(request=request):
                try:
                    app_name = secret.labels.get("app")
                    if app_name:
                        secret_data = await self.get_api_key(app_name)
                        if secret_data:
                            secrets.append(secret_data)
                except Exception as e:
                    logger.error(f"Error processing secret {secret.name}: {str(e)}")
                    continue

            return secrets

        except Exception as e:
            logger.error(f"Error listing API keys: {str(e)}")
            raise

    async def update_api_key(self, app_name: str, new_credentials: Dict) -> Dict:
        """Update existing API key with new credentials"""
        try:
            # Get existing secret data
            current_data = await self.get_api_key(app_name)
            if not current_data:
                raise ValueError(f"No existing secret found for app: {app_name}")

            # Update credentials and rotation timestamps
            rotation_period = current_data["metadata"]["rotation_period_days"]
            updated_data = {
                "credentials": new_credentials,
                "metadata": {
                    "created_at": current_data["metadata"]["created_at"],
                    "last_rotated": datetime.now().isoformat(),
                    "next_rotation": (datetime.now() + timedelta(days=rotation_period)).isoformat(),
                    "rotation_period_days": rotation_period
                }
            }

            # Store updated data
            return await self.store_api_key(app_name, new_credentials, rotation_period)

        except Exception as e:
            logger.error(f"Error updating API key for {app_name}: {str(e)}")
            raise