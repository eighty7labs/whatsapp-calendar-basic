from openai import AsyncOpenAI
from config import config
from models.schemas import OpenAITaskAnalysis, EditRequest
import json
import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for handling OpenAI API interactions"""
    
    def __init__(self):
        if not config.OPENAI_API_KEY or "your_" in config.OPENAI_API_KEY.lower():
            logger.error("OpenAI API key not configured")
            self.client = None
        else:
            self.client = self._initialize_client()
        
        self.model = config.OPENAI_MODEL
        self.max_tokens = config.OPENAI_MAX_TOKENS
        self.temperature = config.OPENAI_TEMPERATURE
        self.top_p = config.OPENAI_TOP_P
        self.max_retries = 3
        self.retry_delay = 1.0
    
    def _initialize_client(self):
        """Initialize OpenAI client with version compatibility handling"""
        try:
            # First, let's check what version we're working with
            import openai
            logger.info(f"OpenAI library version: {getattr(openai, '__version__', 'unknown')}")
            
            # Try to create a custom HTTP client that doesn't have the proxies issue
            try:
                import httpx
                
                # Create a custom HTTP client without problematic parameters
                http_client = httpx.AsyncClient(
                    timeout=30.0,
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=100)
                )
                
                # Initialize OpenAI client with custom HTTP client
                client = AsyncOpenAI(
                    api_key=config.OPENAI_API_KEY,
                    http_client=http_client
                )
                
                logger.info("OpenAI client initialized with custom HTTP client")
                return client
                
            except Exception as e:
                logger.warning(f"Custom HTTP client approach failed: {str(e)}")
            
            # Fallback: Try with minimal parameters and monkey-patch if needed
            try:
                # Try to patch the AsyncOpenAI class to remove problematic parameters
                original_init = AsyncOpenAI.__init__
                
                def patched_init(self, api_key=None, **kwargs):
                    # Remove problematic parameters
                    safe_kwargs = {}
                    safe_params = ['api_key', 'base_url', 'timeout', 'max_retries', 'http_client']
                    
                    for key, value in kwargs.items():
                        if key in safe_params:
                            safe_kwargs[key] = value
                    
                    if api_key:
                        safe_kwargs['api_key'] = api_key
                    
                    return original_init(self, **safe_kwargs)
                
                # Temporarily patch the init method
                AsyncOpenAI.__init__ = patched_init
                
                try:
                    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
                    logger.info("OpenAI client initialized with patched initialization")
                    return client
                finally:
                    # Restore original init method
                    AsyncOpenAI.__init__ = original_init
                    
            except Exception as e:
                logger.warning(f"Patched initialization failed: {str(e)}")
            
            # Last resort: Try to use synchronous client and wrap it
            try:
                from openai import OpenAI
                
                # Create synchronous client first
                sync_client = OpenAI(api_key=config.OPENAI_API_KEY)
                
                # Create a wrapper that mimics async behavior
                class AsyncOpenAIWrapper:
                    def __init__(self, sync_client):
                        self.sync_client = sync_client
                        self.chat = AsyncChatWrapper(sync_client.chat)
                
                class AsyncChatWrapper:
                    def __init__(self, sync_chat):
                        self.sync_chat = sync_chat
                        self.completions = AsyncCompletionsWrapper(sync_chat.completions)
                
                class AsyncCompletionsWrapper:
                    def __init__(self, sync_completions):
                        self.sync_completions = sync_completions
                    
                    async def create(self, **kwargs):
                        # Run synchronous call in thread pool
                        import asyncio
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(
                            None, 
                            lambda: self.sync_completions.create(**kwargs)
                        )
                
                client = AsyncOpenAIWrapper(sync_client)
                logger.info("OpenAI client initialized with sync-to-async wrapper")
                return client
                
            except Exception as e:
                logger.warning(f"Sync-to-async wrapper failed: {str(e)}")
            
            # If everything fails, return None
            logger.error("All OpenAI client initialization methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Critical error in OpenAI client initialization: {str(e)}")
            return None
    
    async def _make_api_call(self, messages: list, max_tokens: int = None, temperature: float = None, top_p: float = None) -> Optional[str]:
        """Make API call with retry logic"""
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None
        
        import openai
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature or self.temperature,
                    top_p=top_p or self.top_p,
                    max_tokens=max_tokens or self.max_tokens,
                    timeout=30.0
                )
                
                return response.choices[0].message.content.strip()
            
            except openai.AuthenticationError as e:
                logger.error(f"OpenAI Authentication Error: {e}. Check your API key.")
                return None # No point in retrying auth errors
            except openai.RateLimitError as e:
                logger.error(f"OpenAI Rate Limit Error: {e}. Please check your plan and billing details.")
                return None # No point in retrying rate limit errors
            except Exception as e:
                logger.warning(f"OpenAI API attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"OpenAI API failed after {self.max_retries} attempts: {str(e)}")
                    return None
    
    def _safe_json_parse(self, content: str, fallback_data: dict) -> dict:
        """Safely parse JSON with fallback"""
        if not content:
            return fallback_data
        
        try:
            # Try to parse as-is
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                try:
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    json_str = content[start:end].strip()
                    return json.loads(json_str)
                except (json.JSONDecodeError, ValueError):
                    pass
            
            # Try to extract JSON from the content
            try:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                pass
            
            logger.error(f"Failed to parse JSON from OpenAI response: {content}")
            return fallback_data
    
    async def analyze_task_message(self, message: str) -> OpenAITaskAnalysis:
        """Analyze a message to determine if it contains a task and extract information"""
        
        system_prompt = """You are an expert at extracting the intent from the user message, and classify it as a task that can be added to a to-do list. If the user input relates to self harm or any malicious intent, then say that you cannot proceed. 

Secondly, your job is to extract the following information from the user's message:
1) task title: what is the task to do?
2) when does the task need to be done. Extract the time and date. If it is not clear whether the task needs to be done in the before noon or after noon, clarify from the user.

If the user message is not classified as a task, respond by saying - "Not sure if that is a task? Would you still want to add that to your calendar?". If the user says yes, then add the original message to the calendar event title, and proceed to gather other information.

If he user does not provide these details in the original message, then ask the user for this information by saying - "When do you want to {task}"?

If any user message related to edit or change or modify the details provided earlier, ask the user for the new information.

Create a response with all the details to confirm with the user. The details should be in the following format only:

RESPONSE FORMAT (JSON only):
{
    "is_task": boolean,
    "extracted_info": {
        "title": "clear, concise task title",
        "date": "extracted date (today/tomorrow/Monday/2024-01-15)",
        "time": "extracted time (3pm/15:00/morning/evening)",
        "duration": "duration if mentioned (1 hour/30 minutes)",
        "description": "additional context or details"
    },
    "suggested_questions": ["questions for missing critical info"]
}

Keep the default duration as 30 mins for all tasks. 
"""

        try:
            content = await self._make_api_call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze: '{message}'"}
            ])
            
            fallback_data = {
                "is_task": False,
                "extracted_info": {},
                "suggested_questions": []
            }
            
            analysis_data = self._safe_json_parse(content, fallback_data)
            
            # Validate and clean the data
            analysis_data.setdefault("is_task", False)
            analysis_data.setdefault("extracted_info", {})
            analysis_data.setdefault("suggested_questions", [])
            
            return OpenAITaskAnalysis(**analysis_data)
                
        except Exception as e:
            logger.error(f"Error in analyze_task_message: {str(e)}")
            return OpenAITaskAnalysis(
                is_task=False,
                extracted_info={},
                suggested_questions=[]
            )
    
    async def parse_user_response(self, message: str, context: str) -> Dict[str, Any]:
        """Parse user response in context of ongoing conversation"""
        
        system_prompt = f"""You are parsing user responses in a task scheduling conversation.

Context: {context}

Extract relevant information from the user's response. Focus on:
- Dates: today, tomorrow, Monday, next Friday, December 25, 25th
- Times: 3pm, 15:00, morning, evening, afternoon, noon
- Durations: 1 hour, 30 minutes, 2 hours, half hour

RESPONSE FORMAT (JSON only):
{{
    "date": "parsed date if provided",
    "time": "parsed time if provided", 
    "duration": "duration in standard format (e.g., '60 minutes')",
    "other_info": "any other relevant details"
}}

Only include fields that are clearly mentioned in the user's message."""

        try:
            content = await self._make_api_call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ], max_tokens=300)
            
            return self._safe_json_parse(content, {})
                
        except Exception as e:
            logger.error(f"Error in parse_user_response: {str(e)}")
            return {}
    
    async def generate_follow_up_question(self, missing_field: str, task_data: Dict[str, Any]) -> str:
        """Generate a natural follow-up question for missing information"""
        
        task_title = task_data.get('title', 'your task')
        
        question_templates = {
            'date': f"What date would you like to schedule '{task_title}'? You can say something like 'tomorrow', 'next Friday', or a specific date.",
            'time': f"What time works best for '{task_title}'? You can specify like '3pm', '15:00', or 'morning'.",
            'duration': f"How long should I block for '{task_title}'? For example, '1 hour' or '30 minutes'."
        }
        
        return question_templates.get(missing_field, f"Could you provide more details about {missing_field}?")

    async def parse_confirmation_modification(self, message: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a user's response during confirmation to see if they want to modify the task."""
        
        system_prompt = f"""You are an expert at understanding user requests to modify an in-progress task. The user is confirming a task and has provided a message that is not a simple 'yes' or 'no'. Analyze their message for any changes to the task details.

Current Task Details:
{json.dumps(task_data, indent=2)}

User's Message:
"{message}"

RESPONSE FORMAT (JSON only):
{{
    "title": "new title if changed",
    "date": "new date if changed",
    "time": "new time if changed",
    "duration": "new duration if changed"
}}

Only include fields the user wants to change. If the message is not a modification request, return an empty JSON object.
"""
        try:
            content = await self._make_api_call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ], max_tokens=300)
            
            return self._safe_json_parse(content, {})
                
        except Exception as e:
            logger.error(f"Error in parse_confirmation_modification: {str(e)}")
            return None
    
    async def analyze_edit_request(self, message: str, recent_events: list = None) -> EditRequest:
        """Analyze a message to determine if it's an edit request for an existing event"""
        
        events_context = ""
        if recent_events:
            events_context = "\nRecent events:\n"
            for i, event in enumerate(recent_events[:3]):
                events_context += f"{i+1}. '{event.title}' on {event.date} at {event.time}\n"
        
        system_prompt = f"""You are an expert at detecting event edit requests. Analyze messages to identify if the user wants to modify an existing calendar event.

EDIT INDICATORS:
- Edit words: change, update, modify, edit, reschedule, move, shift
- Field references: time, title, name, duration, length, date, day
- Event references: meeting, appointment, event, last event, my meeting, the call

EXAMPLES OF EDIT REQUESTS:
✓ "Change my meeting time to 4pm"
✓ "Update the title to 'Sprint Planning'"
✓ "Make the duration 2 hours"
✓ "Edit my last event"
✓ "Reschedule the team meeting to tomorrow"
✓ "Move my 3pm call to 5pm"
✓ "Change the meeting name"

EXAMPLES OF NON-EDIT REQUESTS:
✗ "Schedule a new meeting"
✗ "What's my next appointment?"
✗ "Cancel my meeting"
✗ "How are you?"

{events_context}

RESPONSE FORMAT (JSON only):
{{
    "is_edit": boolean,
    "edit_type": "title|time|duration|date|multiple",
    "new_value": "extracted new value if clear",
    "event_reference": "which event to edit (last|recent|specific title)",
    "extracted_info": {{
        "field_to_edit": "specific field name",
        "new_title": "new title if changing title",
        "new_time": "new time if changing time", 
        "new_duration": "new duration if changing duration",
        "new_date": "new date if changing date",
        "event_identifier": "how user referred to the event"
    }}
}}

Be conservative - only mark as edit if you're confident. Extract all available information."""

        try:
            content = await self._make_api_call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze: '{message}'"}
            ])
            
            fallback_data = {
                "is_edit": False,
                "edit_type": None,
                "new_value": None,
                "event_reference": None,
                "extracted_info": {}
            }
            
            edit_data = self._safe_json_parse(content, fallback_data)
            
            # Validate and clean the data
            edit_data.setdefault("is_edit", False)
            edit_data.setdefault("edit_type", None)
            edit_data.setdefault("new_value", None)
            edit_data.setdefault("event_reference", None)
            edit_data.setdefault("extracted_info", {})
            
            return EditRequest(**edit_data)
                
        except Exception as e:
            logger.error(f"Error in analyze_edit_request: {str(e)}")
            return EditRequest(
                is_edit=False,
                edit_type=None,
                new_value=None,
                event_reference=None,
                extracted_info={}
            )

    async def analyze_query_message(self, message: str) -> Dict[str, Any]:
        """Analyze a message to determine if it's a query about existing events."""
        
        system_prompt = """You are an expert at understanding user queries about their calendar events. Your job is to determine if the user is asking for a list of events and to extract the date range for the query.

QUERY INDICATORS:
- "what events", "do I have", "what's on my calendar", "show me my events"
- Date references: today, tomorrow, this week, next month, Friday

RESPONSE FORMAT (JSON only):
{
    "is_query": boolean,
    "query_type": "list_events",
    "date_range": "today|tomorrow|this week|next week|this month|next month|specific_date"
}

If the user is asking for events on a specific day, set "date_range" to the specific day (e.g., "Friday", "2024-01-15"). If it's not a query, return is_query: false."""

        try:
            content = await self._make_api_call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze: '{message}'"}
            ])
            
            fallback_data = {
                "is_query": False,
                "query_type": None,
                "date_range": None
            }
            
            query_data = self._safe_json_parse(content, fallback_data)
            
            # Validate and clean the data
            query_data.setdefault("is_query", False)
            query_data.setdefault("query_type", None)
            query_data.setdefault("date_range", None)
            
            return query_data
                
        except Exception as e:
            logger.error(f"Error in analyze_query_message: {str(e)}")
            return {
                "is_query": False,
                "query_type": None,
                "date_range": None
            }

# Global OpenAI service instance
openai_service = OpenAIService()
