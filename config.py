import os
import logging
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Config:
    # Twilio Configuration
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")  # Updated to more reliable model
    OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "10000"))
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.0"))
    OPENAI_TOP_P = float(os.getenv("OPENAI_TOP_P", "0.2"))
    
    # Google Calendar Configuration
    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google_credentials.json")
    GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./whatsapp_bot.db")
    
    # Redis Configuration (for session management)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    USE_REDIS = os.getenv("USE_REDIS", "False").lower() == "true"
    
    # Application Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # Timezone
    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Calcutta")
    
    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Session Configuration
    SESSION_TIMEOUT_HOURS = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))
    
    @classmethod
    def validate_config(cls):
        """Validate that all required environment variables are set"""
        required_vars = [
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN", 
            "OPENAI_API_KEY",
            "GOOGLE_CALENDAR_ID"
        ]
        
        missing_vars = []
        placeholder_vars = []
        
        for var in required_vars:
            value = getattr(cls, var)
            if not value:
                missing_vars.append(var)
            elif "your_" in str(value).lower() or "here" in str(value).lower():
                placeholder_vars.append(var)
        
        errors = []
        if missing_vars:
            errors.append(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        if placeholder_vars:
            errors.append(f"Placeholder values detected for: {', '.join(placeholder_vars)}. Please update with actual values.")
        
        # Validate Google credentials file exists only if base64 creds are not provided
        if not cls.GOOGLE_CREDENTIALS_BASE64 and cls.GOOGLE_CREDENTIALS_PATH and not Path(cls.GOOGLE_CREDENTIALS_PATH).exists():
            errors.append(f"Google credentials file not found: {cls.GOOGLE_CREDENTIALS_PATH}")
        
        if errors:
            raise ValueError("\n".join(errors))
        
        return True
    
    @classmethod
    def setup_logging(cls):
        """Setup application logging"""
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL.upper()),
            format=cls.LOG_FORMAT,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('app.log') if cls.ENVIRONMENT == 'production' else logging.NullHandler()
            ]
        )
        
        # Set specific loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("google").setLevel(logging.WARNING)
        
        return logging.getLogger(__name__)

# Create config instance
config = Config()
