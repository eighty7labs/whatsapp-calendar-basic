from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import pytz
from config import config
from models.schemas import CalendarEvent
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CalendarService:
    """Service for handling Google Calendar API interactions"""
    
    def __init__(self):
        self.calendar_id = config.GOOGLE_CALENDAR_ID
        self.credentials_path = config.GOOGLE_CREDENTIALS_PATH
        self.timezone = pytz.timezone(config.DEFAULT_TIMEZONE)
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Calendar service"""
        try:
            # Define the scopes
            SCOPES = ['https://www.googleapis.com/auth/calendar']
            
            if config.GOOGLE_CREDENTIALS_BASE64:
                import base64
                import json
                creds_json = json.loads(base64.b64decode(config.GOOGLE_CREDENTIALS_BASE64))
                credentials = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
            else:
                # Load credentials from service account file
                credentials = Credentials.from_service_account_file(
                    self.credentials_path, 
                    scopes=SCOPES
                )
            
            # Build the service
            self.service = build('calendar', 'v3', credentials=credentials)
            logger.info("Google Calendar service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar service: {str(e)}")
            self.service = None
    
    def parse_datetime_string(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Parse date and time strings into datetime object with improved natural language support"""
        try:
            now = datetime.now(self.timezone)
            target_date = None
            target_time = None
            
            # Parse date
            target_date = self._parse_date_string(date_str, now)
            if not target_date:
                logger.error(f"Could not parse date: {date_str}")
                return None
            
            # Parse time
            target_time = self._parse_time_string(time_str)
            if not target_time:
                logger.error(f"Could not parse time: {time_str}")
                return None
            
            # Combine date and time
            target_datetime = datetime.combine(target_date, target_time)
            
            # Localize to timezone
            localized_dt = self.timezone.localize(target_datetime)
            
            # Ensure the datetime is in the future (unless it's today)
            if localized_dt < now and target_date != now.date():
                logger.warning(f"Parsed datetime {localized_dt} is in the past")
            
            return localized_dt
            
        except Exception as e:
            logger.error(f"Error parsing datetime: {str(e)}")
            return None
    
    def _parse_date_string(self, date_str: str, now: datetime) -> Optional[datetime.date]:
        """Parse date string with natural language support"""
        date_str = date_str.lower().strip()
        
        # Handle relative dates
        if date_str == "today":
            return now.date()
        elif date_str == "tomorrow":
            return (now + timedelta(days=1)).date()
        elif date_str == "day after tomorrow":
            return (now + timedelta(days=2)).date()
        elif date_str == "yesterday":
            return (now - timedelta(days=1)).date()
        
        # Handle weekdays
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
        }
        
        for day_name, day_num in weekdays.items():
            if day_name in date_str:
                days_ahead = day_num - now.weekday()
                if "next" in date_str:
                    if days_ahead <= 0: # if it's "next Sunday" on a Sunday
                        days_ahead += 7
                elif days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                return (now + timedelta(days=days_ahead)).date()
        
        # Handle "next week", "next month"
        if "next week" in date_str:
            return (now + timedelta(days=7)).date()
        elif "next month" in date_str:
            return (now + timedelta(days=30)).date()
        
        # Handle specific date formats
        date_formats = [
            "%Y-%m-%d",      # 2024-01-15
            "%d/%m/%Y",      # 15/01/2024
            "%m/%d/%Y",      # 01/15/2024
            "%d-%m-%Y",      # 15-01-2024
            "%m-%d-%Y",      # 01-15-2024
            "%B %d, %Y",     # January 15, 2024
            "%b %d, %Y",     # Jan 15, 2024
            "%d %B %Y",      # 15 January 2024
            "%d %b %Y",      # 15 Jan 2024
            "%B %d",         # January 15 (current year)
            "%b %d",         # Jan 15 (current year)
            "%d %B",         # 15 January (current year)
            "%d %b",         # 15 Jan (current year)
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # If no year specified, assume current year
                if parsed_date.year == 1900:
                    parsed_date = parsed_date.replace(year=now.year)
                return parsed_date.date()
            except ValueError:
                continue
        
        # Handle ordinal dates like "15th", "1st", "22nd"
        import re
        ordinal_match = re.search(r'(\d{1,2})(st|nd|rd|th)', date_str)
        if ordinal_match:
            day = int(ordinal_match.group(1))
            try:
                # Assume current month and year
                target_date = now.replace(day=day).date()
                # If the date has passed this month, assume next month
                if target_date < now.date():
                    if now.month == 12:
                        target_date = target_date.replace(year=now.year + 1, month=1)
                    else:
                        target_date = target_date.replace(month=now.month + 1)
                return target_date
            except ValueError:
                pass
        
        return None
    
    def _parse_time_string(self, time_str: str) -> Optional[datetime.time]:
        """Parse time string with natural language support"""
        time_str = time_str.lower().strip()
        
        # Handle phrases like "6 in the morning"
        import re
        match = re.search(r'(\d{1,2})\s*(?:o\'clock)?\s*(in the\s*)?(morning|afternoon|evening)', time_str)
        if match:
            hour = int(match.group(1))
            period = match.group(3)
            
            if period == 'afternoon' and hour < 12:
                hour += 12
            elif period == 'evening' and hour < 12:
                hour += 12
            
            try:
                return datetime.time(hour, 0)
            except ValueError:
                pass

        # Handle relative times
        time_mappings = {
            'morning': '09:00',
            'early morning': '07:00',
            'late morning': '11:00',
            'noon': '12:00',
            'afternoon': '14:00',
            'early afternoon': '13:00',
            'late afternoon': '16:00',
            'evening': '18:00',
            'early evening': '17:00',
            'late evening': '20:00',
            'night': '21:00',
            'midnight': '00:00',
        }
        
        for phrase, time_24h in time_mappings.items():
            if phrase in time_str:
                return datetime.strptime(time_24h, "%H:%M").time()
        
        # Handle specific time formats
        time_formats = [
            "%H:%M",         # 14:30
            "%H.%M",         # 14.30
            "%I:%M %p",      # 2:30 PM
            "%I:%M%p",       # 2:30PM
            "%I %p",         # 2 PM
            "%I%p",          # 2PM
            "%H",            # 14
        ]
        
        for fmt in time_formats:
            try:
                return datetime.strptime(time_str, fmt).time()
            except ValueError:
                continue
        
        # Handle special cases like "3pm", "10am"
        import re
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)
            
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
            
            try:
                return datetime.time(hour, minute)
            except ValueError:
                pass
        
        # Handle 24-hour format without colon
        if time_str.isdigit() and len(time_str) in [3, 4]:
            try:
                if len(time_str) == 3:  # e.g., "930" -> "9:30"
                    hour = int(time_str[0])
                    minute = int(time_str[1:3])
                else:  # e.g., "1430" -> "14:30"
                    hour = int(time_str[:2])
                    minute = int(time_str[2:4])
                return datetime.time(hour, minute)
            except ValueError:
                pass
        
        return None
    
    async def create_event(self, task_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Create a calendar event from task data and return both event ID and URL"""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return None
        
        try:
            # Parse datetime
            start_datetime = self.parse_datetime_string(
                task_data.get('date', ''), 
                task_data.get('time', '')
            )
            
            if not start_datetime:
                logger.error("Could not parse start datetime")
                return None
            
            # Calculate end datetime
            duration_minutes = task_data.get('duration', 60)  # Default 1 hour
            if isinstance(duration_minutes, str):
                import re
                numbers = re.findall(r'(\d+\.?\d*)', duration_minutes)
                if numbers:
                    total_minutes = 0
                    if "hour" in duration_minutes.lower():
                        total_minutes += float(numbers[0]) * 60
                    if "minute" in duration_minutes.lower():
                        total_minutes += float(numbers[-1])
                    duration_minutes = total_minutes or 60
                else:
                    duration_minutes = 60
            
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            
            # Create event object
            event = {
                'summary': task_data.get('title', 'Untitled Task'),
                'description': task_data.get('description', ''),
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': str(self.timezone),
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': str(self.timezone),
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 15},
                        {'method': 'email', 'minutes': 60},
                    ],
                },
            }
            
            # Add location if provided
            if task_data.get('location'):
                event['location'] = task_data['location']
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            event_id = created_event.get('id')
            event_url = created_event.get('htmlLink')
            
            logger.info(f"Event created successfully: {event_id}")
            
            return {
                'event_id': event_id,
                'event_url': event_url
            }
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return None
    
    def format_event_confirmation(self, task_data: Dict[str, Any], event_url: str) -> str:
        """Format a confirmation message for the created event"""
        title = task_data.get('title', 'Your task')
        date = task_data.get('date', '')
        time = task_data.get('time', '')
        duration = task_data.get('duration', 60)
        
        # Format duration
        if isinstance(duration, int):
            if duration >= 60:
                hours = duration // 60
                minutes = duration % 60
                if minutes > 0:
                    duration_str = f"{hours}h {minutes}m"
                else:
                    duration_str = f"{hours}h"
            else:
                duration_str = f"{duration}m"
        else:
            duration_str = str(duration)
        
        message = f"✅ Perfect! I've added '{title}' to your Google Calendar.\n\n"
        message += f"📅 Date: {date}\n"
        message += f"⏰ Time: {time}\n"
        message += f"⏱️ Duration: {duration_str}\n\n"
        message += f"You'll receive reminders 15 minutes and 1 hour before the event.\n\n"
        message += f"View in calendar: {event_url}"
        
        return message
    
    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an event from Google Calendar"""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return None
        
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            return event
            
        except HttpError as e:
            logger.error(f"Google Calendar API error getting event: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error getting calendar event: {str(e)}")
            return None
    
    async def update_event(self, event_id: str, updates: Dict[str, Any]) -> Optional[str]:
        """Update an existing calendar event"""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return None
        
        try:
            # First, get the existing event
            existing_event = await self.get_event(event_id)
            if not existing_event:
                logger.error(f"Event {event_id} not found")
                return None
            
            # Apply updates to the event
            updated_event = existing_event.copy()
            
            # Handle title updates
            if 'title' in updates:
                updated_event['summary'] = updates['title']
            
            # Handle time/date updates
            if 'date' in updates or 'time' in updates:
                # Get current start time
                current_start = existing_event['start'].get('dateTime')
                if current_start:
                    current_dt = datetime.fromisoformat(current_start.replace('Z', '+00:00'))
                    current_dt = current_dt.astimezone(self.timezone)
                    
                    # Use existing date/time if not provided in updates
                    date_str = updates.get('date', current_dt.strftime('%Y-%m-%d'))
                    time_str = updates.get('time', current_dt.strftime('%H:%M'))
                    
                    # Parse new datetime
                    new_start_dt = self.parse_datetime_string(date_str, time_str)
                    if new_start_dt:
                        # Calculate duration from existing event
                        current_end = existing_event['end'].get('dateTime')
                        if current_end:
                            current_end_dt = datetime.fromisoformat(current_end.replace('Z', '+00:00'))
                            current_start_dt = datetime.fromisoformat(current_start.replace('Z', '+00:00'))
                            duration = current_end_dt - current_start_dt
                        else:
                            duration = timedelta(hours=1)  # Default 1 hour
                        
                        new_end_dt = new_start_dt + duration
                        
                        updated_event['start'] = {
                            'dateTime': new_start_dt.isoformat(),
                            'timeZone': str(self.timezone),
                        }
                        updated_event['end'] = {
                            'dateTime': new_end_dt.isoformat(),
                            'timeZone': str(self.timezone),
                        }
            
            # Handle duration updates
            if 'duration' in updates:
                duration_minutes = updates['duration']
                if isinstance(duration_minutes, str):
                    import re
                    numbers = re.findall(r'(\d+\.?\d*)', duration_minutes)
                    if numbers:
                        total_minutes = 0
                        if "hour" in duration_minutes.lower():
                            total_minutes += float(numbers[0]) * 60
                        if "minute" in duration_minutes.lower():
                            total_minutes += float(numbers[-1])
                        duration_minutes = total_minutes or 60
                    else:
                        duration_minutes = 60
                
                # Update end time based on new duration
                start_time = updated_event['start'].get('dateTime')
                if start_time:
                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    if start_dt.tzinfo is None:
                        start_dt = self.timezone.localize(start_dt)
                    
                    new_end_dt = start_dt + timedelta(minutes=duration_minutes)
                    updated_event['end'] = {
                        'dateTime': new_end_dt.isoformat(),
                        'timeZone': str(self.timezone),
                    }
            
            # Update the event in Google Calendar
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=updated_event
            ).execute()
            
            logger.info(f"Event {event_id} updated successfully")
            return updated_event.get('htmlLink')
            
        except HttpError as e:
            logger.error(f"Google Calendar API error updating event: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error updating calendar event: {str(e)}")
            return None
    
    def format_event_update_confirmation(self, event_title: str, updates: Dict[str, Any], event_url: str) -> str:
        """Format a confirmation message for event updates"""
        message = f"✅ Updated '{event_title}' successfully!\n\n"
        
        if 'title' in updates:
            message += f"📝 New title: {updates['title']}\n"
        if 'date' in updates:
            message += f"📅 New date: {updates['date']}\n"
        if 'time' in updates:
            message += f"⏰ New time: {updates['time']}\n"
        if 'duration' in updates:
            duration = updates['duration']
            if isinstance(duration, int):
                if duration >= 60:
                    hours = duration // 60
                    minutes = duration % 60
                    if minutes > 0:
                        duration_str = f"{hours}h {minutes}m"
                    else:
                        duration_str = f"{hours}h"
                else:
                    duration_str = f"{duration}m"
            else:
                duration_str = str(duration)
            message += f"⏱️ New duration: {duration_str}\n"
        
        message += f"\nView updated event: {event_url}"
        
        return message

    async def list_events(self, date_range: str) -> str:
        """List events from the calendar based on a date range."""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return "Sorry, I can't access your calendar right now."

        now = datetime.now(self.timezone)
        time_min = now
        time_max = None

        if date_range == "today":
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = now.replace(hour=23, minute=59, second=59, microsecond=0)
        elif date_range == "tomorrow":
            tomorrow = now + timedelta(days=1)
            time_min = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)
        elif "week" in date_range:
            start_of_week = now - timedelta(days=now.weekday())
            if "next" in date_range:
                start_of_week += timedelta(days=7)
            end_of_week = start_of_week + timedelta(days=6)
            time_min = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = end_of_week.replace(hour=23, minute=59, second=59, microsecond=0)
        else: # specific day
            target_date = self._parse_date_string(date_range, now)
            if target_date:
                time_min = self.timezone.localize(datetime.combine(target_date, datetime.min.time()))
                time_max = self.timezone.localize(datetime.combine(target_date, datetime.max.time()))
            else:
                return f"Sorry, I couldn't understand the date '{date_range}'."


        try:
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])

            if not events:
                return f"You have no events scheduled for {date_range}."

            response = f"Here are your events for {date_range}:\n\n"
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(self.timezone)
                response += f"- *{event['summary']}* at {start_dt.strftime('%I:%M %p')}\n"
            
            return response

        except HttpError as e:
            logger.error(f"Google Calendar API error: {str(e)}")
            return "Sorry, I encountered an error while fetching your events."
        except Exception as e:
            logger.error(f"Error listing calendar events: {str(e)}")
            return "An unexpected error occurred."

# Global calendar service instance
calendar_service = CalendarService()
