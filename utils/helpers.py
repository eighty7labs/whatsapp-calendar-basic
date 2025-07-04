from datetime import datetime, timedelta
import re
from typing import Optional, Tuple
import pytz

def parse_relative_date(date_string: str, timezone_str: str = "UTC") -> Optional[datetime]:
    """Parse relative date strings like 'tomorrow', 'next Friday', etc."""
    
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)
    date_string = date_string.lower().strip()
    
    # Handle today/tomorrow
    if date_string == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_string == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Handle "next [day]"
    if date_string.startswith("next "):
        day_name = date_string[5:]
        days_of_week = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        if day_name in days_of_week:
            target_weekday = days_of_week[day_name]
            current_weekday = now.weekday()
            days_ahead = target_weekday - current_weekday
            
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            
            target_date = now + timedelta(days=days_ahead)
            return target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return None

def parse_relative_time(time_string: str) -> Optional[Tuple[int, int]]:
    """Parse relative time strings like 'morning', 'afternoon', 'evening'."""
    
    time_string = time_string.lower().strip()
    
    time_mappings = {
        'morning': (9, 0),
        'afternoon': (14, 0),
        'evening': (18, 0),
        'night': (20, 0),
        'noon': (12, 0),
        'midnight': (0, 0)
    }
    
    if time_string in time_mappings:
        return time_mappings[time_string]
    
    # Try to parse time formats like "3pm", "15:30", etc.
    # This is a basic implementation - the calendar service has more comprehensive parsing
    time_patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)?',  # 3:30pm, 15:30
        r'(\d{1,2})\s*(am|pm)',          # 3pm, 3am
        r'(\d{1,2})$'                    # 15 (24-hour format)
    ]
    
    for pattern in time_patterns:
        match = re.match(pattern, time_string)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if len(match.groups()) > 1 and match.group(2) else 0
            
            # Handle AM/PM
            if len(match.groups()) > 2 and match.group(3):
                period = match.group(3).lower()
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)
    
    return None

def format_duration(minutes: int) -> str:
    """Format duration in minutes to human-readable string."""
    
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours}h"
    else:
        return f"{hours}h {remaining_minutes}m"

def extract_phone_number(whatsapp_number: str) -> str:
    """Extract clean phone number from WhatsApp format."""
    
    # Remove 'whatsapp:' prefix if present
    if whatsapp_number.startswith('whatsapp:'):
        whatsapp_number = whatsapp_number[9:]
    
    # Remove any non-digit characters except +
    clean_number = re.sub(r'[^\d+]', '', whatsapp_number)
    
    return clean_number

def validate_calendar_id(calendar_id: str) -> bool:
    """Validate Google Calendar ID format."""
    
    # Basic validation - should be an email-like format or 'primary'
    if calendar_id == 'primary':
        return True
    
    # Check if it looks like an email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, calendar_id))

def sanitize_message(message: str) -> str:
    """Sanitize user message for processing."""
    
    # Remove excessive whitespace
    message = re.sub(r'\s+', ' ', message.strip())
    
    # Remove common WhatsApp artifacts
    message = re.sub(r'^\[.*?\]\s*', '', message)  # Remove timestamps
    
    return message

def is_business_hours(dt: datetime, timezone_str: str = "UTC") -> bool:
    """Check if datetime falls within business hours (9 AM - 6 PM)."""
    
    tz = pytz.timezone(timezone_str)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    
    # Check if it's a weekday (Monday = 0, Sunday = 6)
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Check if it's within business hours
    return 9 <= dt.hour < 18

def get_next_business_day(dt: datetime, timezone_str: str = "UTC") -> datetime:
    """Get the next business day from given datetime."""
    
    tz = pytz.timezone(timezone_str)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    
    # Start from the next day
    next_day = dt + timedelta(days=1)
    
    # Find next weekday
    while next_day.weekday() >= 5:  # Skip weekends
        next_day += timedelta(days=1)
    
    # Set to 9 AM
    return next_day.replace(hour=9, minute=0, second=0, microsecond=0)
