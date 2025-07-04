from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ConversationState(str, Enum):
    IDLE = "idle"
    TASK_DETECTED = "task_detected"
    AWAITING_DATE = "awaiting_date"
    AWAITING_TIME = "awaiting_time"
    AWAITING_DURATION = "awaiting_duration"
    CONFIRMING = "confirming"
    EDITING_EVENT = "editing_event"
    AWAITING_EDIT_FIELD = "awaiting_edit_field"
    AWAITING_NEW_VALUE = "awaiting_new_value"
    CONFIRMING_EDIT = "confirming_edit"
    SELECTING_EVENT = "selecting_event"

class TwilioWebhookRequest(BaseModel):
    From: str = Field(..., description="WhatsApp number of the sender")
    Body: str = Field(..., description="Message content")
    MessageSid: str = Field(..., description="Unique message identifier")
    AccountSid: str = Field(..., description="Twilio account SID")
    To: Optional[str] = Field(None, description="WhatsApp number of the recipient")
    NumMedia: Optional[str] = Field("0", description="Number of media attachments")

class TaskRequest(BaseModel):
    title: str = Field(..., description="Task title/summary")
    date: Optional[str] = Field(None, description="Task date")
    time: Optional[str] = Field(None, description="Task time")
    duration: Optional[int] = Field(None, description="Duration in minutes")
    description: Optional[str] = Field(None, description="Additional task description")

class CalendarEvent(BaseModel):
    summary: str = Field(..., description="Event title")
    start_datetime: datetime = Field(..., description="Event start time")
    end_datetime: datetime = Field(..., description="Event end time")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")

class ConversationSession(BaseModel):
    user_phone: str = Field(..., description="User's WhatsApp number")
    state: ConversationState = Field(ConversationState.IDLE, description="Current conversation state")
    task_data: Dict[str, Any] = Field(default_factory=dict, description="Collected task information")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")

class OpenAITaskAnalysis(BaseModel):
    is_task: bool = Field(..., description="Whether the message contains a task")
    extracted_info: Dict[str, Any] = Field(default_factory=dict, description="Extracted task information")
    suggested_questions: list[str] = Field(default_factory=list, description="Questions to ask for missing info")

class WhatsAppResponse(BaseModel):
    message: str = Field(..., description="Response message to send")
    to_number: str = Field(..., description="Recipient WhatsApp number")

class StoredEvent(BaseModel):
    event_id: str = Field(..., description="Google Calendar event ID")
    title: str = Field(..., description="Event title")
    date: str = Field(..., description="Event date")
    time: str = Field(..., description="Event time")
    duration: str = Field(..., description="Event duration")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When event was created")
    calendar_url: Optional[str] = Field(None, description="Google Calendar event URL")

class EditRequest(BaseModel):
    is_edit: bool = Field(..., description="Whether the message is an edit request")
    edit_type: Optional[str] = Field(None, description="Type of edit: 'title', 'time', 'duration', 'date'")
    new_value: Optional[str] = Field(None, description="New value for the field")
    event_reference: Optional[str] = Field(None, description="Reference to which event to edit")
    extracted_info: Dict[str, Any] = Field(default_factory=dict, description="Extracted edit information")
