from twilio.rest import Client
from twilio.request_validator import RequestValidator
from twilio.base.exceptions import TwilioRestException
from config import config
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class TwilioService:
    """Service for handling Twilio WhatsApp API interactions"""
    
    def __init__(self):
        if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN:
            logger.error("Twilio credentials not configured")
            self.client = None
            self.validator = None
        else:
            try:
                self.client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
                self.validator = RequestValidator(config.TWILIO_AUTH_TOKEN)
                logger.info("Twilio service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio service: {str(e)}")
                self.client = None
                self.validator = None
        
        self.whatsapp_number = config.TWILIO_WHATSAPP_NUMBER
        self.max_message_length = 1600  # WhatsApp message limit
        self.retry_attempts = 3
        self.retry_delay = 1.0
    
    def send_message(self, to_number: str, message: str) -> bool:
        """Send a WhatsApp message to a user with retry logic"""
        if not self.client:
            logger.error("Twilio client not initialized")
            return False
        
        try:
            # Ensure the to_number has the whatsapp: prefix
            if not to_number.startswith('whatsapp:'):
                to_number = f'whatsapp:{to_number}'
            
            # Truncate message if too long
            if len(message) > self.max_message_length:
                message = message[:self.max_message_length - 3] + "..."
                logger.warning(f"Message truncated to {self.max_message_length} characters")
            
            # Attempt to send with retries
            for attempt in range(self.retry_attempts):
                try:
                    sent_message = self.client.messages.create(
                        body=message,
                        from_=self.whatsapp_number,
                        to=to_number
                    )
                    
                    logger.info(f"Message sent successfully to {self.format_phone_number(to_number)}. SID: {sent_message.sid}")
                    return True
                    
                except TwilioRestException as e:
                    if e.status == 429:  # Rate limit
                        logger.warning(f"Rate limited, attempt {attempt + 1}/{self.retry_attempts}")
                        if attempt < self.retry_attempts - 1:
                            time.sleep(self.retry_delay * (attempt + 1))
                            continue
                    elif e.status in [400, 404]:  # Bad request or not found
                        logger.error(f"Twilio error {e.status}: {e.msg}")
                        return False
                    else:
                        logger.error(f"Twilio REST exception: {e.status} - {e.msg}")
                        if attempt < self.retry_attempts - 1:
                            time.sleep(self.retry_delay)
                            continue
                    return False
                    
                except Exception as e:
                    logger.error(f"Unexpected error sending message (attempt {attempt + 1}): {str(e)}")
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            return False
    
    def send_message_chunks(self, to_number: str, message: str) -> bool:
        """Send long messages in chunks"""
        if len(message) <= self.max_message_length:
            return self.send_message(to_number, message)
        
        # Split message into chunks
        chunks = []
        current_chunk = ""
        
        for line in message.split('\n'):
            if len(current_chunk + line + '\n') > self.max_message_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'
                else:
                    # Single line is too long, split it
                    chunks.append(line[:self.max_message_length - 3] + "...")
            else:
                current_chunk += line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Send chunks with small delay
        success = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.5)  # Small delay between chunks
            
            chunk_message = f"({i+1}/{len(chunks)}) {chunk}" if len(chunks) > 1 else chunk
            if not self.send_message(to_number, chunk_message):
                success = False
                break
        
        return success
    
    def validate_webhook(self, url: str, params: dict, signature: str) -> bool:
        """Validate that the webhook request is from Twilio"""
        if not self.validator:
            logger.warning("Twilio validator not initialized, skipping validation")
            return True  # Allow in development
        
        try:
            return self.validator.validate(url, params, signature)
        except Exception as e:
            logger.error(f"Webhook validation failed: {str(e)}")
            return False
    
    def format_phone_number(self, phone_number: str) -> str:
        """Format phone number for WhatsApp (remove whatsapp: prefix if present)"""
        if phone_number.startswith('whatsapp:'):
            return phone_number[9:]  # Remove 'whatsapp:' prefix
        return phone_number
    
    def get_message_status(self, message_sid: str) -> Optional[str]:
        """Get the status of a sent message"""
        if not self.client:
            return None
        
        try:
            message = self.client.messages(message_sid).fetch()
            return message.status
        except Exception as e:
            logger.error(f"Failed to get message status: {str(e)}")
            return None
    
    def send_typing_indicator(self, to_number: str) -> bool:
        """Send typing indicator to show bot is processing (if supported)"""
        # Note: WhatsApp Business API doesn't support typing indicators
        # This is a placeholder for future functionality
        return True

# Global Twilio service instance
twilio_service = TwilioService()
