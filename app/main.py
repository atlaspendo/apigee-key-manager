# main.py
import os
from datetime import datetime, timedelta
from typing import Dict, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.cloud import secretmanager
from google.oauth2 import service_account
from apscheduler.schedulers.background import BackgroundScheduler
from pydantic import BaseModel
import logging
import json

# Configuration
class Config:
    ROTATION_PERIOD_DAYS = int(os.getenv("ROTATION_PERIOD_DAYS", "30"))
    APIGEE_ORG = os.getenv("APIGEE_ORG")
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

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

# Initialize clients
credentials = service_account.Credentials.from_service_account_file(Config.CREDENTIALS_PATH)
secret_manager = secretmanager.SecretManagerServiceClient(credentials=credentials)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ApigeeKeyManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    async def rotate_secret(self, app_name: str) -> AppSecret:
        """Rotate API key and secret for a specific app"""
        try:
            # Generate new credentials in Apigee
            new_credentials = await self._generate_new_credentials(app_name)
            
            # Update Secret Manager
            await self._update_secret_manager(app_name, new_credentials)
            
            logger.info(f"Successfully rotated secrets for {app_name}")
            
            return AppSecret(
                app_name=app_name,
                consumer_key=new_credentials["key"],
                consumer_secret=new_credentials["secret"],
                last_rotated=datetime.now(),
                next_rotation=datetime.now() + timedelta(days=Config.ROTATION_PERIOD_DAYS)
            )
        except Exception as e:
            logger.error(f"Error rotating secret for {app_name}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _generate_new_credentials(self, app_name: str) -> Dict:
        """Generate new credentials in Apigee"""
        # Implementation would use Apigee API to generate new credentials
        # This is a placeholder for the actual implementation
        pass

    async def _update_secret_manager(self, app_name: str, credentials: Dict):
        """Update secret in Google Secret Manager"""
        secret_path = f"projects/{Config.PROJECT_ID}/secrets/{app_name}/versions"
        secret_data = json.dumps(credentials).encode("UTF-8")
        
        try:
            secret_manager.add_secret_version(
                request={
                    "parent": secret_path,
                    "payload": {"data": secret_data},
                }
            )
            logger.info(f"Updated secret in Secret Manager for {app_name}")
        except Exception as e:
            logger.error(f"Error updating secret in Secret Manager: {str(e)}")
            raise

    def schedule_rotation(self, app_name: str, period_days: int):
        """Schedule periodic rotation for an app"""
        self.scheduler.add_job(
            self.rotate_secret,
            'interval',
            days=period_days,
            id=f"rotation_{app_name}",
            args=[app_name],
            replace_existing=True
        )
        logger.info(f"Scheduled rotation for {app_name} every {period_days} days")

# Initialize key manager
key_manager = ApigeeKeyManager()

# API Routes
@app.post("/apps/{app_name}/rotate")
async def rotate_app_secret(app_name: str, background_tasks: BackgroundTasks):
    """Trigger immediate rotation for an app"""
    background_tasks.add_task(key_manager.rotate_secret, app_name)
    return {"message": f"Secret rotation initiated for {app_name}"}

@app.post("/apps/{app_name}/schedule")
async def set_rotation_schedule(app_name: str, schedule: RotationSchedule):
    """Set rotation schedule for an app"""
    key_manager.schedule_rotation(app_name, schedule.rotation_period_days)
    return {"message": f"Rotation schedule set for {app_name}"}

@app.get("/apps/{app_name}")
async def get_app_status(app_name: str) -> AppSecret:
    """Get current status of an app's secrets"""
    # Implementation would fetch current status from Secret Manager
    pass

# UI Routes and Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
