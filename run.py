# run.py
import uvicorn
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """
    Run the FastAPI application using uvicorn
    """
    try:
        logger.info("Starting ApigeeX Key Manager")
        
        # Check if required directories exist
        if not os.path.exists("app"):
            raise Exception("app directory not found!")
        
        if not os.path.exists("app/static"):
            raise Exception("app/static directory not found!")
        
        # Run the application
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            reload_dirs=["app"],
            log_level="info"
        )
    
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise

if __name__ == "__main__":
    main()