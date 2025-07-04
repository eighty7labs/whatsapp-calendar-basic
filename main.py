from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from config import config

# Setup logging
logger = config.setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting WhatsApp Task Bot...")
    
    try:
        # Validate configuration
        config.validate_config()
        logger.info("Configuration validation passed")
        
        # Test service connections
        await test_service_connections()
        logger.info("Service connection tests passed")
        
    except Exception as e:
        logger.error(f"Startup validation failed: {str(e)}")
        if config.ENVIRONMENT == "production":
            raise e
        else:
            logger.warning("Continuing in development mode despite validation errors")
    
    yield
    
    # Shutdown
    logger.info("Shutting down WhatsApp Task Bot...")

app = FastAPI(
    title="WhatsApp Task Bot",
    description="A WhatsApp bot that detects tasks and adds them to Google Calendar",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from routers import webhook
app.include_router(webhook.router, prefix="/webhook")

async def test_service_connections():
    """Test connections to external services"""
    from services.openai_service import openai_service
    from services.calendar_service import calendar_service
    from services.twilio_service import twilio_service
    
    # Test OpenAI connection
    try:
        test_analysis = await openai_service.analyze_task_message("test message")
        logger.info("OpenAI service connection: OK")
    except Exception as e:
        logger.warning(f"OpenAI service connection failed: {str(e)}")
    
    # Test Google Calendar service
    try:
        if calendar_service.service:
            logger.info("Google Calendar service connection: OK")
        else:
            logger.warning("Google Calendar service not initialized")
    except Exception as e:
        logger.warning(f"Google Calendar service connection failed: {str(e)}")
    
    # Test Twilio service
    try:
        if twilio_service.client:
            logger.info("Twilio service connection: OK")
        else:
            logger.warning("Twilio service not initialized")
    except Exception as e:
        logger.warning(f"Twilio service connection failed: {str(e)}")

# Health check endpoints
@app.get("/")
async def root():
    return {
        "message": "WhatsApp Task Bot is running",
        "status": "healthy",
        "version": "1.0.0",
        "environment": config.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    """Detailed health check with service status"""
    health_status = {
        "status": "healthy",
        "timestamp": os.environ.get("TIMESTAMP", "unknown"),
        "services": {}
    }
    
    # Check OpenAI service
    try:
        from services.openai_service import openai_service
        if openai_service.client:
            health_status["services"]["openai"] = "connected"
        else:
            health_status["services"]["openai"] = "disconnected"
    except Exception:
        health_status["services"]["openai"] = "error"
    
    # Check Google Calendar service
    try:
        from services.calendar_service import calendar_service
        if calendar_service.service:
            health_status["services"]["google_calendar"] = "connected"
        else:
            health_status["services"]["google_calendar"] = "disconnected"
    except Exception:
        health_status["services"]["google_calendar"] = "error"
    
    # Check Twilio service
    try:
        from services.twilio_service import twilio_service
        if twilio_service.client:
            health_status["services"]["twilio"] = "connected"
        else:
            health_status["services"]["twilio"] = "disconnected"
    except Exception:
        health_status["services"]["twilio"] = "error"
    
    # Determine overall status
    service_statuses = list(health_status["services"].values())
    if "error" in service_statuses:
        health_status["status"] = "degraded"
    elif "disconnected" in service_statuses:
        health_status["status"] = "partial"
    
    return health_status

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return PlainTextResponse(
        "Internal server error", 
        status_code=500
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level=config.LOG_LEVEL.lower()
    )
