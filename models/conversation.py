from typing import Dict, Any, Optional, List
from datetime import datetime
from models.schemas import ConversationState, ConversationSession, StoredEvent

class ConversationManager:
    """Manages conversation sessions for WhatsApp users"""
    
    def __init__(self):
        # In-memory storage for development
        # In production, this should be replaced with Redis or database
        self.sessions: Dict[str, ConversationSession] = {}
        self.user_events: Dict[str, List[StoredEvent]] = {}  # Store recent events per user
    
    def get_session(self, user_phone: str) -> ConversationSession:
        """Get or create a conversation session for a user"""
        if user_phone not in self.sessions:
            self.sessions[user_phone] = ConversationSession(
                user_phone=user_phone,
                state=ConversationState.IDLE,
                task_data={},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        return self.sessions[user_phone]
    
    def update_session_state(self, user_phone: str, new_state: ConversationState) -> None:
        """Update the conversation state for a user"""
        session = self.get_session(user_phone)
        session.state = new_state
        session.updated_at = datetime.now()
    
    def update_task_data(self, user_phone: str, key: str, value: Any) -> None:
        """Update task data for a user session"""
        session = self.get_session(user_phone)
        session.task_data[key] = value
        session.updated_at = datetime.utcnow()
    
    def get_task_data(self, user_phone: str) -> Dict[str, Any]:
        """Get task data for a user session"""
        session = self.get_session(user_phone)
        return session.task_data
    
    def clear_session(self, user_phone: str) -> None:
        """Clear/reset a user's conversation session"""
        if user_phone in self.sessions:
            self.sessions[user_phone] = ConversationSession(
                user_phone=user_phone,
                state=ConversationState.IDLE,
                task_data={},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
    
    def is_task_complete(self, user_phone: str) -> bool:
        """Check if all required task information has been collected"""
        task_data = self.get_task_data(user_phone)
        required_fields = ['title', 'date', 'time']
        
        return all(field in task_data and task_data[field] for field in required_fields)
    
    def get_missing_fields(self, user_phone: str) -> list[str]:
        """Get list of missing required fields for a task"""
        task_data = self.get_task_data(user_phone)
        required_fields = ['title', 'date', 'time']
        
        missing = []
        for field in required_fields:
            if field not in task_data or not task_data[field]:
                missing.append(field)
        
        return missing
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> None:
        """Clean up old conversation sessions"""
        current_time = datetime.now()
        expired_sessions = []
        
        for user_phone, session in self.sessions.items():
            age_hours = (current_time - session.updated_at).total_seconds() / 3600
            if age_hours > max_age_hours:
                expired_sessions.append(user_phone)
        
        for user_phone in expired_sessions:
            del self.sessions[user_phone]
    
    def store_event(self, user_phone: str, event: StoredEvent) -> None:
        """Store a created event for a user"""
        if user_phone not in self.user_events:
            self.user_events[user_phone] = []
        
        # Add new event to the beginning of the list
        self.user_events[user_phone].insert(0, event)
        
        # Keep only the last 10 events per user
        if len(self.user_events[user_phone]) > 10:
            self.user_events[user_phone] = self.user_events[user_phone][:10]
    
    def get_recent_events(self, user_phone: str, limit: int = 5) -> List[StoredEvent]:
        """Get recent events for a user"""
        if user_phone not in self.user_events:
            return []
        
        return self.user_events[user_phone][:limit]
    
    def get_event_by_index(self, user_phone: str, index: int) -> Optional[StoredEvent]:
        """Get an event by its index in the recent events list"""
        events = self.get_recent_events(user_phone)
        if 0 <= index < len(events):
            return events[index]
        return None
    
    def get_event_by_id(self, user_phone: str, event_id: str) -> Optional[StoredEvent]:
        """Get an event by its Google Calendar event ID"""
        if user_phone not in self.user_events:
            return None
        
        for event in self.user_events[user_phone]:
            if event.event_id == event_id:
                return event
        return None
    
    def update_stored_event(self, user_phone: str, event_id: str, updates: Dict[str, Any]) -> bool:
        """Update a stored event with new information"""
        if user_phone not in self.user_events:
            return False
        
        for i, event in enumerate(self.user_events[user_phone]):
            if event.event_id == event_id:
                # Update the event with new values
                for key, value in updates.items():
                    if hasattr(event, key):
                        setattr(event, key, value)
                return True
        return False
    
    def find_event_by_title_partial(self, user_phone: str, partial_title: str) -> Optional[StoredEvent]:
        """Find an event by partial title match"""
        if user_phone not in self.user_events:
            return None
        
        partial_title = partial_title.lower()
        for event in self.user_events[user_phone]:
            if partial_title in event.title.lower():
                return event
        return None

# Global conversation manager instance
conversation_manager = ConversationManager()
