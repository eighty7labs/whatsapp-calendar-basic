from fastapi import APIRouter, Request, Form, HTTPException, Header
from fastapi.responses import PlainTextResponse
from typing import Annotated, Optional
import logging
import time

from models.schemas import ConversationState, StoredEvent
from models.conversation import conversation_manager
from services.twilio_service import twilio_service
from services.openai_service import openai_service
from services.calendar_service import calendar_service
from config import config
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/whatsapp")
async def handle_whatsapp_webhook(
    request: Request,
    From: Annotated[str, Form()],
    Body: Annotated[str, Form()],
    MessageSid: Annotated[str, Form()],
    AccountSid: Annotated[str, Form()],
    To: Annotated[str, Form()] = None,
    NumMedia: Annotated[str, Form()] = "0",
    X_Twilio_Signature: Annotated[Optional[str], Header()] = None
):
    """Handle incoming WhatsApp messages from Twilio"""
    
    start_time = time.time()
    user_phone = None
    
    try:
        # Format phone number for logging
        user_phone = twilio_service.format_phone_number(From)
        
        # Log incoming message with details
        logger.info(f"Webhook received - From: {user_phone}, MessageSid: {MessageSid}, Body: '{Body[:100]}{'...' if len(Body) > 100 else ''}'")
        
        # Validate webhook signature in production
        if config.ENVIRONMENT == "production" and X_Twilio_Signature:
            url = str(request.url)
            form_data = await request.form()
            params = dict(form_data)
            
            if not twilio_service.validate_webhook(url, params, X_Twilio_Signature):
                logger.warning(f"Invalid webhook signature from {user_phone}")
                return PlainTextResponse("Forbidden", status_code=403)
        
        # Skip media messages for now
        if NumMedia and int(NumMedia) > 0:
            logger.info(f"Media message received from {user_phone}, sending help message")
            response_message = "I can help you schedule tasks, but I can't process media files yet. Please send me a text message describing what you'd like to schedule! 😊"
            twilio_service.send_message(From, response_message)
            return PlainTextResponse("OK", status_code=200)
        
        # Validate message content
        if not Body or not Body.strip():
            logger.warning(f"Empty message received from {user_phone}")
            return PlainTextResponse("OK", status_code=200)
        
        # Rate limiting check (simple implementation)
        if not _check_rate_limit(user_phone):
            logger.warning(f"Rate limit exceeded for {user_phone}")
            response_message = "You're sending messages too quickly. Please wait a moment before sending another message."
            twilio_service.send_message(From, response_message)
            return PlainTextResponse("OK", status_code=200)
        
        # Get current conversation session
        session = conversation_manager.get_session(user_phone)
        current_state = session.state
        
        logger.info(f"Processing message from {user_phone} in state: {current_state}")
        
        # Process message based on current conversation state
        response_message = await process_message(user_phone, Body.strip(), current_state)
        
        # Send response
        success = twilio_service.send_message(From, response_message)
        
        processing_time = time.time() - start_time
        
        if success:
            logger.info(f"Response sent to {user_phone} (processed in {processing_time:.2f}s)")
            return PlainTextResponse("OK", status_code=200)
        else:
            logger.error(f"Failed to send response to {user_phone}")
            return PlainTextResponse("Error sending response", status_code=500)
            
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error processing webhook from {user_phone}: {str(e)} (failed after {processing_time:.2f}s)", exc_info=True)
        
        # Try to send error message to user
        try:
            if user_phone:
                error_message = "Sorry, I encountered an error processing your message. Please try again in a moment."
                twilio_service.send_message(From, error_message)
        except:
            logger.error("Failed to send error message to user")
        
        return PlainTextResponse("Internal server error", status_code=500)

# Simple rate limiting (in production, use Redis)
_rate_limit_cache = {}

def _check_rate_limit(user_phone: str, max_messages: int = 10, window_seconds: int = 60) -> bool:
    """Simple rate limiting check"""
    now = time.time()
    
    if user_phone not in _rate_limit_cache:
        _rate_limit_cache[user_phone] = []
    
    # Clean old entries
    _rate_limit_cache[user_phone] = [
        timestamp for timestamp in _rate_limit_cache[user_phone]
        if now - timestamp < window_seconds
    ]
    
    # Check if under limit
    if len(_rate_limit_cache[user_phone]) >= max_messages:
        return False
    
    # Add current request
    _rate_limit_cache[user_phone].append(now)
    return True

async def process_message(user_phone: str, message: str, current_state: ConversationState) -> str:
    """Process incoming message based on conversation state"""
    
    try:
        # Handle cancel/stop commands
        if message.lower().strip() in ['cancel', 'stop', 'quit', 'exit']:
            conversation_manager.clear_session(user_phone)
            return "Task scheduling cancelled. Feel free to send me another task anytime! 😊"
        
        # Handle help commands
        if message.lower().strip() in ['help', 'info', 'commands']:
            return get_help_message()
        
        # Process based on current state
        if current_state == ConversationState.IDLE:
            return await handle_idle_state(user_phone, message)
        
        elif current_state == ConversationState.TASK_DETECTED:
            return await handle_task_detected_state(user_phone, message)
        
        elif current_state == ConversationState.AWAITING_DATE:
            return await handle_awaiting_date_state(user_phone, message)
        
        elif current_state == ConversationState.AWAITING_TIME:
            return await handle_awaiting_time_state(user_phone, message)
        
        elif current_state == ConversationState.AWAITING_DURATION:
            return await handle_awaiting_duration_state(user_phone, message)
        
        elif current_state == ConversationState.CONFIRMING:
            return await handle_confirming_state(user_phone, message)
        
        elif current_state == ConversationState.SELECTING_EVENT:
            return await handle_selecting_event_state(user_phone, message)
        
        else:
            # Unknown state, reset to idle
            conversation_manager.clear_session(user_phone)
            return "Something went wrong. Let's start over. Please send me a task you'd like to schedule! 😊"
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        conversation_manager.clear_session(user_phone)
        return "Sorry, I encountered an error. Please try again with your task."

async def handle_idle_state(user_phone: str, message: str) -> str:
    """Handle message when user is in idle state"""
    
    # First, check if the user is asking for a list of events
    query_analysis = await openai_service.analyze_query_message(message)
    if query_analysis.get("is_query"):
        date_range = query_analysis.get("date_range", "today")
        return await calendar_service.list_events(date_range)

    # If not a query, check for an edit request
    recent_events = conversation_manager.get_recent_events(user_phone)
    edit_analysis = await openai_service.analyze_edit_request(message, recent_events)
    
    if edit_analysis.is_edit:
        # This is an edit request
        return await handle_edit_request(user_phone, message, edit_analysis)
    
    # If not an edit, check for new task
    analysis = await openai_service.analyze_task_message(message)
    
    if analysis.is_task:
        # Task detected, extract information
        task_data = analysis.extracted_info
        
        # Store extracted information
        for key, value in task_data.items():
            if value:  # Only store non-empty values
                conversation_manager.update_task_data(user_phone, key, value)
        
        # Check what information is missing
        missing_fields = conversation_manager.get_missing_fields(user_phone)
        
        if not missing_fields:
            # All information available, move to confirmation
            conversation_manager.update_session_state(user_phone, ConversationState.CONFIRMING)
            return await get_confirmation_message(user_phone)
        else:
            # Ask for missing information
            conversation_manager.update_session_state(user_phone, ConversationState.TASK_DETECTED)
            return await ask_for_missing_info(user_phone, missing_fields[0])
    
    else:
        # Not a task or edit, provide helpful response
        help_msg = ("I help you schedule tasks and add them to your Google Calendar! 📅\n\n"
                   "📝 Create new events:\n"
                   "• 'Remind me to call John tomorrow at 3pm'\n"
                   "• 'Meeting with team on Friday'\n"
                   "• 'Doctor appointment next Tuesday at 10am'\n\n")
        
        if recent_events:
            help_msg += ("✏️ Edit existing events:\n"
                        "• 'Change my meeting time to 4pm'\n"
                        "• 'Update the title to Sprint Planning'\n"
                        "• 'Make the duration 2 hours'\n\n")
        
        help_msg += "What would you like to do?"
        return help_msg

async def handle_task_detected_state(user_phone: str, message: str) -> str:
    """Handle message when task is detected and collecting info"""
    
    # Parse user response for missing information
    task_data = conversation_manager.get_task_data(user_phone)
    context = f"User is providing information for task: {task_data.get('title', 'unknown task')}"
    
    parsed_info = await openai_service.parse_user_response(message, context)
    
    # Update task data with parsed information
    for key, value in parsed_info.items():
        if value and key != 'other_info':
            conversation_manager.update_task_data(user_phone, key, value)
    
    # Check what's still missing
    missing_fields = conversation_manager.get_missing_fields(user_phone)
    
    if not missing_fields:
        # All information collected, move to confirmation
        conversation_manager.update_session_state(user_phone, ConversationState.CONFIRMING)
        return await get_confirmation_message(user_phone)
    else:
        # Still missing information, ask for next field
        return await ask_for_missing_info(user_phone, missing_fields[0])

async def handle_awaiting_date_state(user_phone: str, message: str) -> str:
    """Handle message when waiting for date"""
    conversation_manager.update_task_data(user_phone, 'date', message.strip())
    
    missing_fields = conversation_manager.get_missing_fields(user_phone)
    if not missing_fields:
        conversation_manager.update_session_state(user_phone, ConversationState.CONFIRMING)
        return await get_confirmation_message(user_phone)
    else:
        conversation_manager.update_session_state(user_phone, ConversationState.TASK_DETECTED)
        return await ask_for_missing_info(user_phone, missing_fields[0])

async def handle_awaiting_time_state(user_phone: str, message: str) -> str:
    """Handle message when waiting for time"""
    conversation_manager.update_task_data(user_phone, 'time', message.strip())
    
    missing_fields = conversation_manager.get_missing_fields(user_phone)
    if not missing_fields:
        conversation_manager.update_session_state(user_phone, ConversationState.CONFIRMING)
        return await get_confirmation_message(user_phone)
    else:
        conversation_manager.update_session_state(user_phone, ConversationState.TASK_DETECTED)
        return await ask_for_missing_info(user_phone, missing_fields[0])

async def handle_awaiting_duration_state(user_phone: str, message: str) -> str:
    """Handle message when waiting for duration"""
    conversation_manager.update_task_data(user_phone, 'duration', message.strip())
    conversation_manager.update_session_state(user_phone, ConversationState.CONFIRMING)
    return await get_confirmation_message(user_phone)

async def handle_confirming_state(user_phone: str, message: str) -> str:
    """Handle message when confirming task details"""
    
    response = message.lower().strip()
    task_data = conversation_manager.get_task_data(user_phone)
    
    if response in ['yes', 'y', 'confirm', 'ok', 'correct', 'right', 'good']:
        # Create calendar event
        created_event = await calendar_service.create_event(task_data)
        
        if created_event:
            event_id = created_event.get('event_id')
            event_url = created_event.get('event_url')
            
            stored_event = StoredEvent(
                event_id=event_id,
                title=task_data.get('title', 'Untitled Task'),
                date=task_data.get('date', ''),
                time=task_data.get('time', ''),
                duration=str(task_data.get('duration', '1 hour')),
                calendar_url=event_url
            )
            conversation_manager.store_event(user_phone, stored_event)
            
            confirmation_msg = calendar_service.format_event_confirmation(task_data, event_url)
            conversation_manager.clear_session(user_phone)
            return confirmation_msg
        else:
            conversation_manager.clear_session(user_phone)
            return ("Sorry, I couldn't create the calendar event. Please check your Google Calendar settings and try again.\n\n"
                    "Feel free to send me another task! 😊")
    
    elif response in ['no', 'n', 'cancel', 'wrong', 'incorrect']:
        conversation_manager.clear_session(user_phone)
        return "No problem! Let's start over. Please send me your task again with the correct details. 😊"
    
    else:
        # Check for modifications
        modifications = await openai_service.parse_confirmation_modification(message, task_data)
        
        if modifications:
            for key, value in modifications.items():
                if value:
                    conversation_manager.update_task_data(user_phone, key, value)
            
            # Ask for confirmation again with updated details
            return await get_confirmation_message(user_phone)
        else:
            # Unclear response, ask again
            return await get_confirmation_message(user_phone)

async def ask_for_missing_info(user_phone: str, missing_field: str) -> str:
    """Ask user for missing information"""
    task_data = conversation_manager.get_task_data(user_phone)
    
    if missing_field == 'date':
        conversation_manager.update_session_state(user_phone, ConversationState.AWAITING_DATE)
        return await openai_service.generate_follow_up_question('date', task_data)
    
    elif missing_field == 'time':
        conversation_manager.update_session_state(user_phone, ConversationState.AWAITING_TIME)
        return await openai_service.generate_follow_up_question('time', task_data)
    
    elif missing_field == 'duration':
        conversation_manager.update_session_state(user_phone, ConversationState.AWAITING_DURATION)
        return await openai_service.generate_follow_up_question('duration', task_data)
    
    else:
        return f"Could you provide more details about {missing_field}?"

async def get_confirmation_message(user_phone: str) -> str:
    """Generate confirmation message for task details"""
    task_data = conversation_manager.get_task_data(user_phone)
    
    title = task_data.get('title', 'Your task')
    date = task_data.get('date', 'Not specified')
    time = task_data.get('time', 'Not specified')
    duration = task_data.get('duration', '1 hour')
    
    message = f"Great! Let me confirm the details:\n\n"
    message += f"📝 Task: {title}\n"
    message += f"📅 Date: {date}\n"
    message += f"⏰ Time: {time}\n"
    message += f"⏱️ Duration: {duration}\n\n"
    message += f"Should I add this to your Google Calendar? Reply 'yes' to confirm or 'no' to cancel."
    
    return message

async def handle_selecting_event_state(user_phone: str, message: str) -> str:
    """Handle message when user is selecting an event to edit"""
    
    try:
        # Get the pending edit analysis
        task_data = conversation_manager.get_task_data(user_phone)
        pending_edit_data = task_data.get('pending_edit')
        
        if not pending_edit_data:
            conversation_manager.clear_session(user_phone)
            return "Something went wrong. Please try your edit request again."
        
        # Parse the user's selection
        try:
            selection = int(message.strip())
        except ValueError:
            return "Please reply with a number (1-5) to select which event you want to edit."
        
        # Get recent events
        recent_events = conversation_manager.get_recent_events(user_phone)
        
        if selection < 1 or selection > min(len(recent_events), 5):
            return f"Please choose a number between 1 and {min(len(recent_events), 5)}."
        
        # Get the selected event
        selected_event = recent_events[selection - 1]
        
        # Recreate the edit analysis from stored data
        from models.schemas import EditRequest
        edit_analysis = EditRequest(**pending_edit_data)
        
        # Clear the session and apply the edit
        conversation_manager.clear_session(user_phone)
        
        return await apply_event_edit(user_phone, selected_event, edit_analysis)
        
    except Exception as e:
        logger.error(f"Error in handle_selecting_event_state: {str(e)}")
        conversation_manager.clear_session(user_phone)
        return "Sorry, I encountered an error. Please try your edit request again."

async def handle_edit_request(user_phone: str, message: str, edit_analysis) -> str:
    """Handle edit requests for existing events"""
    
    try:
        recent_events = conversation_manager.get_recent_events(user_phone)
        
        if not recent_events:
            return ("I don't see any recent events to edit. Please create an event first, then you can edit it!\n\n"
                   "Try: 'Schedule a meeting tomorrow at 2pm'")
        
        # Try to identify which event to edit
        target_event = None
        
        # Check if user specified a particular event
        event_ref = edit_analysis.event_reference
        extracted_info = edit_analysis.extracted_info
        
        if event_ref == "last" or "last" in message.lower():
            # Edit the most recent event
            target_event = recent_events[0]
        elif extracted_info.get("event_identifier"):
            # Try to find event by partial title match
            identifier = extracted_info["event_identifier"].lower()
            for event in recent_events:
                if identifier in event.title.lower():
                    target_event = event
                    break
        
        # If no specific event found, check if there's only one recent event
        if not target_event and len(recent_events) == 1:
            target_event = recent_events[0]
        
        # If still no target event, ask user to choose
        if not target_event:
            return await show_event_selection(user_phone, recent_events, edit_analysis)
        
        # Apply the edit
        return await apply_event_edit(user_phone, target_event, edit_analysis)
        
    except Exception as e:
        logger.error(f"Error handling edit request: {str(e)}")
        return "Sorry, I encountered an error while trying to edit your event. Please try again."



async def show_event_selection(user_phone: str, events, edit_analysis) -> str:
    """Show user a list of events to choose from for editing"""
    
    # Store the edit analysis for when user selects an event
    conversation_manager.update_task_data(user_phone, 'pending_edit', edit_analysis.dict())
    conversation_manager.update_session_state(user_phone, ConversationState.SELECTING_EVENT)
    
    message = "Which event would you like to edit?\n\n"
    
    for i, event in enumerate(events[:5], 1):
        message += f"{i}. '{event.title}' on {event.date} at {event.time}\n"
    
    message += f"\nReply with the number (1-{min(len(events), 5)}) of the event you want to edit."
    
    return message

async def apply_event_edit(user_phone: str, event: StoredEvent, edit_analysis) -> str:
    """Apply the edit to the specified event"""
    
    try:
        # Prepare updates based on edit analysis
        updates = {}
        extracted_info = edit_analysis.extracted_info
        
        # Determine what to update based on edit type and extracted info
        if edit_analysis.edit_type == "title" or extracted_info.get("new_title"):
            updates["title"] = extracted_info.get("new_title") or edit_analysis.new_value
        
        elif edit_analysis.edit_type == "time" or extracted_info.get("new_time"):
            updates["time"] = extracted_info.get("new_time") or edit_analysis.new_value
        
        elif edit_analysis.edit_type == "duration" or extracted_info.get("new_duration"):
            updates["duration"] = extracted_info.get("new_duration") or edit_analysis.new_value
        
        elif edit_analysis.edit_type == "date" or extracted_info.get("new_date"):
            updates["date"] = extracted_info.get("new_date") or edit_analysis.new_value
        
        elif edit_analysis.edit_type == "multiple":
            # Handle multiple field updates
            for field in ["new_title", "new_time", "new_duration", "new_date"]:
                if extracted_info.get(field):
                    field_name = field.replace("new_", "")
                    updates[field_name] = extracted_info[field]
        
        if not updates:
            return f"I'm not sure what you want to change about '{event.title}'. Could you be more specific?\n\nFor example: 'Change the time to 4pm' or 'Update the title to Team Meeting'"
        
        # Update the event in Google Calendar
        updated_url = await calendar_service.update_event(event.event_id, updates)
        
        if updated_url:
            # Update stored event
            conversation_manager.update_stored_event(user_phone, event.event_id, updates)
            
            # Format confirmation message
            confirmation_msg = calendar_service.format_event_update_confirmation(
                event.title, updates, updated_url
            )
            
            return confirmation_msg
        else:
            return f"Sorry, I couldn't update '{event.title}'. Please try again or check your calendar manually."
            
    except Exception as e:
        logger.error(f"Error applying event edit: {str(e)}")
        return "Sorry, I encountered an error while updating your event. Please try again."

def get_help_message() -> str:
    """Get help message"""
    return ("🤖 WhatsApp Task Bot Help\n\n"
            "I can help you schedule tasks and add them to your Google Calendar!\n\n"
            "📝 Create Events:\n"
            "• 'Remind me to call John tomorrow at 3pm'\n"
            "• 'Meeting with team on Friday at 2pm'\n"
            "• 'Doctor appointment next Tuesday at 10am'\n"
            "• 'Lunch with Sarah on Monday'\n\n"
            "✏️ Edit Events:\n"
            "• 'Change my meeting time to 4pm'\n"
            "• 'Update the title to Sprint Planning'\n"
            "• 'Make the duration 2 hours'\n"
            "• 'Reschedule to tomorrow'\n\n"
            "🔧 Commands:\n"
            "• 'help' - Show this help message\n"
            "• 'cancel' - Cancel current operation\n\n"
            "Just send me a message describing what you want to do! 😊")
