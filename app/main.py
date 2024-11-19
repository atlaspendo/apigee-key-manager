# app/main.py
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from google.cloud import secretmanager_v1
from google.api_core import exceptions
from pydantic import BaseModel, validator
import logging
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the current directory
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Ensure static directory exists
os.makedirs(STATIC_DIR, exist_ok=True)

# Configuration
class Config:
    ROTATION_PERIOD_DAYS = int(os.getenv("ROTATION_PERIOD_DAYS", "30"))
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"
    CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class AppSecret(BaseModel):
    app_name: str
    consumer_key: str
    consumer_secret: str
    last_rotated: datetime
    next_rotation: datetime

class RotationSchedule(BaseModel):
    app_name: str
    rotation_period_days: int

    @validator('rotation_period_days')
    def validate_period(cls, v):
        if v < 1:
            raise ValueError("Rotation period must be at least 1 day")
        if v > 365:
            raise ValueError("Rotation period cannot exceed 365 days")
        return v

class SecretManager:
    def __init__(self, project_id: str):
        """Initialize Secret Manager with project ID"""
        self.project_id = project_id
        self.client = secretmanager_v1.SecretManagerServiceClient()
        self.parent = f"projects/{project_id}"
        logger.info(f"Initialized Secret Manager for project: {project_id}")

    def create_secret(self, app_name: str, credentials: dict, rotation_period_days: int) -> str:
        """Create a new secret in Google Secret Manager"""
        try:
            secret_id = f"apigee-key-{app_name}"
            
            # Prepare secret data
            secret_data = {
                "credentials": credentials,
                "metadata": {
                    "app_name": app_name,
                    "created_at": datetime.now().isoformat(),
                    "last_rotated": datetime.now().isoformat(),
                    "next_rotation": (datetime.now() + timedelta(days=rotation_period_days)).isoformat(),
                    "rotation_period_days": rotation_period_days
                }
            }

            try:
                # Create new secret
                self.client.create_secret(
                    request={
                        "parent": self.parent,
                        "secret_id": secret_id,
                        "secret": {
                            "replication": {"automatic": {}},
                            "labels": {
                                "type": "apigee-key",
                                "app": app_name,
                                "created_by": "key-manager"
                            }
                        }
                    }
                )
                logger.info(f"Created new secret for app: {app_name}")
            except exceptions.AlreadyExists:
                logger.info(f"Secret already exists for app: {app_name}")

            # Add new version
            secret_path = f"{self.parent}/secrets/{secret_id}"
            version = self.client.add_secret_version(
                request={
                    "parent": secret_path,
                    "payload": {"data": json.dumps(secret_data).encode("UTF-8")}
                }
            )
            
            logger.info(f"Added new version for secret: {secret_id}")
            return version.name

        except Exception as e:
            logger.error(f"Error creating secret for {app_name}: {str(e)}")
            raise

    async def get_secret(self, app_name: str) -> Dict:
        """Get the latest version of a secret"""
        try:
            secret_id = f"apigee-key-{app_name}"
            name = f"{self.parent}/secrets/{secret_id}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            return json.loads(response.payload.data.decode("UTF-8"))
        except exceptions.NotFound:
            logger.error(f"Secret not found for app: {app_name}")
            raise HTTPException(status_code=404, detail=f"Secret not found for app: {app_name}")
        except Exception as e:
            logger.error(f"Error getting secret for {app_name}: {str(e)}")
            raise

    async def list_secrets(self) -> List[Dict]:
        """List all secrets with their metadata"""
        try:
            secrets = []
            request = {"parent": self.parent, "filter": "labels.type=apigee-key"}
            
            for secret in self.client.list_secrets(request=request):
                try:
                    app_name = secret.labels.get("app")
                    if app_name:
                        secret_data = await self.get_secret(app_name)
                        secrets.append(secret_data)
                except Exception as e:
                    logger.error(f"Error processing secret {secret.name}: {str(e)}")
                    continue

            return secrets
        except Exception as e:
            logger.error(f"Error listing secrets: {str(e)}")
            raise

# Initialize FastAPI app
app = FastAPI(title="ApigeeX Key Manager")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Secret Manager
secret_manager = None
if not Config.DEV_MODE and Config.PROJECT_ID:
    try:
        secret_manager = SecretManager(Config.PROJECT_ID)
        logger.info("Secret Manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Secret Manager: {str(e)}")
        raise

class ApigeeKeyManager:
    def __init__(self):
        self.apps_cache = {}

    async def create_app(self, app_name: str, rotation_period_days: int) -> AppSecret:
        """Create a new app with initial credentials"""
        try:
            # Generate initial credentials
            credentials = {
                "key": f"key-{uuid.uuid4()}",
                "secret": f"secret-{uuid.uuid4()}"
            }

            if not Config.DEV_MODE:
                # Store in Secret Manager
                secret_manager.create_secret(
                    app_name=app_name,
                    credentials=credentials,
                    rotation_period_days=rotation_period_days
                )
            
            # Create app secret object
            app_secret = AppSecret(
                app_name=app_name,
                consumer_key=credentials["key"],
                consumer_secret=credentials["secret"],
                last_rotated=datetime.now(),
                next_rotation=datetime.now() + timedelta(days=rotation_period_days)
            )

            self.apps_cache[app_name] = app_secret
            logger.info(f"Successfully created app: {app_name}")
            return app_secret

        except Exception as e:
            logger.error(f"Error creating app {app_name}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def rotate_secret(self, app_name: str) -> AppSecret:
        """Rotate API key and secret"""
        try:
            # Generate new credentials
            new_credentials = {
                "key": f"key-{uuid.uuid4()}",
                "secret": f"secret-{uuid.uuid4()}"
            }

            if not Config.DEV_MODE:
                # Get existing secret to maintain metadata
                existing_secret = await secret_manager.get_secret(app_name)
                rotation_period = existing_secret["metadata"]["rotation_period_days"]
                
                # Store new credentials
                secret_manager.create_secret(
                    app_name=app_name,
                    credentials=new_credentials,
                    rotation_period_days=rotation_period
                )

            # Create updated app secret
            app_secret = AppSecret(
                app_name=app_name,
                consumer_key=new_credentials["key"],
                consumer_secret=new_credentials["secret"],
                last_rotated=datetime.now(),
                next_rotation=datetime.now() + timedelta(days=Config.ROTATION_PERIOD_DAYS)
            )

            self.apps_cache[app_name] = app_secret
            logger.info(f"Successfully rotated secrets for {app_name}")
            return app_secret

        except Exception as e:
            logger.error(f"Error rotating secret for {app_name}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_app_status(self, app_name: str) -> AppSecret:
        """Get current status of an app's secrets"""
        try:
            if not Config.DEV_MODE:
                secret_data = await secret_manager.get_secret(app_name)
                return AppSecret(
                    app_name=app_name,
                    consumer_key=secret_data["credentials"]["key"],
                    consumer_secret=secret_data["credentials"]["secret"],
                    last_rotated=datetime.fromisoformat(secret_data["metadata"]["last_rotated"]),
                    next_rotation=datetime.fromisoformat(secret_data["metadata"]["next_rotation"])
                )
            return self.apps_cache.get(app_name) or await self.create_app(app_name, Config.ROTATION_PERIOD_DAYS)

        except Exception as e:
            logger.error(f"Error getting app status: {str(e)}")
            raise HTTPException(status_code=404, detail=f"App {app_name} not found or error accessing secrets")

# Initialize key manager
key_manager = ApigeeKeyManager()

# Routes
@app.get("/")
async def read_root():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/health")
async def health_check():
    """Check system health"""
    return {
        "status": "healthy",
        "mode": "development" if Config.DEV_MODE else "production",
        "secret_manager": bool(secret_manager),
        "project_id": Config.PROJECT_ID,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/apps/{app_name}/rotate")
async def rotate_app_secret(app_name: str, background_tasks: BackgroundTasks):
    """Rotate API key and secret for an app"""
    return await key_manager.rotate_secret(app_name)

@app.post("/apps/{app_name}/schedule")
async def set_rotation_schedule(app_name: str, schedule: RotationSchedule):
    """Create new app or update rotation schedule"""
    logger.info(f"Received request to create app: {app_name}")
    logger.info(f"Config.DEV_MODE: {Config.DEV_MODE}")
    logger.info(f"Config.PROJECT_ID: {Config.PROJECT_ID}")
    logger.info(f"Secret Manager initialized: {secret_manager is not None}")
    
    try:
        result = await key_manager.create_app(app_name, schedule.rotation_period_days)
        logger.info(f"Successfully created app: {app_name}")
        return result
    except Exception as e:
        logger.error(f"Failed to create app: {str(e)}")
        raise

class SecretManager:
    def create_secret(self, app_name: str, credentials: dict, rotation_period_days: int) -> str:
        """Create a new secret in Google Secret Manager"""
        try:
            logger.info(f"Creating secret for app: {app_name}")
            logger.info(f"Project ID: {self.project_id}")
            
            secret_id = f"apigee-key-{app_name}"
            logger.info(f"Secret ID will be: {secret_id}")
            
            # Prepare secret data
            secret_data = {
                "credentials": credentials,
                "metadata": {
                    "app_name": app_name,
                    "created_at": datetime.now().isoformat(),
                    "last_rotated": datetime.now().isoformat(),
                    "next_rotation": (datetime.now() + timedelta(days=rotation_period_days)).isoformat(),
                    "rotation_period_days": rotation_period_days
                }
            }
            logger.info("Prepared secret data")

            try:
                # Create new secret
                create_request = {
                    "parent": self.parent,
                    "secret_id": secret_id,
                    "secret": {
                        "replication": {"automatic": {}},
                        "labels": {
                            "type": "apigee-key",
                            "app": app_name,
                            "created_by": "key-manager"
                        }
                    }
                }
                logger.info(f"Creating secret with request: {create_request}")
                
                self.client.create_secret(request=create_request)
                logger.info(f"Created new secret for app: {app_name}")
            except exceptions.AlreadyExists:
                logger.info(f"Secret already exists for app: {app_name}")

            # Add new version
            secret_path = f"{self.parent}/secrets/{secret_id}"
            version_request = {
                "parent": secret_path,
                "payload": {"data": json.dumps(secret_data).encode("UTF-8")}
            }
            logger.info("Adding secret version")
            
            version = self.client.add_secret_version(request=version_request)
            logger.info(f"Successfully added version: {version.name}")
            
            return version.name

        except Exception as e:
            logger.error(f"Error creating secret for {app_name}: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {getattr(e, 'details', 'No details available')}")
            raise

class ApigeeKeyManager:
    async def create_app(self, app_name: str, rotation_period_days: int) -> AppSecret:
        """Create a new app with initial credentials"""
        try:
            logger.info(f"Starting app creation: {app_name}")
            logger.info(f"DEV_MODE: {Config.DEV_MODE}")
            
            # Generate initial credentials
            credentials = {
                "key": f"key-{uuid.uuid4()}",
                "secret": f"secret-{uuid.uuid4()}"
            }
            logger.info("Generated credentials")

            if not Config.DEV_MODE and secret_manager:
                logger.info("Using Secret Manager to store credentials")
                # Store in Secret Manager
                secret_manager.create_secret(
                    app_name=app_name,
                    credentials=credentials,
                    rotation_period_days=rotation_period_days
                )
                logger.info("Successfully stored in Secret Manager")
            else:
                logger.info("Skipping Secret Manager (DEV_MODE or no secret_manager)")
            
            # Create app secret object
            app_secret = AppSecret(
                app_name=app_name,
                consumer_key=credentials["key"],
                consumer_secret=credentials["secret"],
                last_rotated=datetime.now(),
                next_rotation=datetime.now() + timedelta(days=rotation_period_days)
            )

            self.apps_cache[app_name] = app_secret
            logger.info(f"Successfully created app: {app_name}")
            return app_secret

        except Exception as e:
            logger.error(f"Error creating app {app_name}: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {getattr(e, 'details', 'No details available')}")
            raise HTTPException(status_code=500, detail=str(e))
        
        
@app.get("/apps/{app_name}")
async def get_app_status(app_name: str) -> AppSecret:
    """Get current status of an app"""
    return await key_manager.get_app_status(app_name)

@app.get("/apps")
async def list_apps() -> List[AppSecret]:
    """List all apps and their status"""
    try:
        if Config.DEV_MODE:
            return list(key_manager.apps_cache.values())
        else:
            secrets = await secret_manager.list_secrets()
            apps = []
            for secret in secrets:
                app_name = secret["metadata"]["app_name"]
                try:
                    app_status = await get_app_status(app_name)
                    apps.append(app_status)
                except Exception as e:
                    logger.error(f"Error processing app {app_name}: {str(e)}")
            return apps
    except Exception as e:
        logger.error(f"Error listing apps: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/verify/{app_name}")
async def verify_app_secret(app_name: str):
    """Verify secret for specific app"""
    if Config.DEV_MODE:
        return {"mode": "development", "message": "Verification not available in dev mode"}
    
    try:
        secret_data = await secret_manager.get_secret(app_name)
        return {
            "exists": True,
            "app_name": app_name,
            "last_rotated": secret_data["metadata"]["last_rotated"],
            "next_rotation": secret_data["metadata"]["next_rotation"],
            "has_credentials": bool(secret_data.get("credentials"))
        }
    except Exception as e:
        return {
            "exists": False,
            "error": str(e)
        }

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)