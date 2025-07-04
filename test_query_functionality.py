import pytest
from unittest.mock import patch, MagicMock
from services.openai_service import OpenAIService
from services.calendar_service import CalendarService
from routers.webhook import handle_idle_state
import asyncio

@pytest.fixture
def openai_service():
    return OpenAIService()

@pytest.fixture
def calendar_service():
    return CalendarService()

@pytest.mark.asyncio
async def test_analyze_query_message(openai_service):
    with patch.object(openai_service, '_make_api_call') as mock_api_call:
        mock_api_call.return_value = '{"is_query": true, "query_type": "list_events", "date_range": "tomorrow"}'
        
        result = await openai_service.analyze_query_message("what events do I have tomorrow?")
        
        assert result["is_query"] is True
        assert result["query_type"] == "list_events"
        assert result["date_range"] == "tomorrow"

@pytest.mark.asyncio
async def test_list_events(calendar_service):
    with patch.object(calendar_service, 'service') as mock_service:
        mock_events_result = {
            "items": [
                {"summary": "Test Event 1", "start": {"dateTime": "2025-07-02T09:00:00+05:30"}},
                {"summary": "Test Event 2", "start": {"dateTime": "2025-07-02T14:00:00+05:30"}},
            ]
        }
        mock_service.events().list().execute.return_value = mock_events_result
        
        result = await calendar_service.list_events("tomorrow")
        
        assert "Here are your events for tomorrow" in result
        assert "Test Event 1" in result
        assert "09:00 AM" in result
        assert "Test Event 2" in result
        assert "02:00 PM" in result

@pytest.mark.asyncio
async def test_webhook_integration_for_query():
    with patch('services.openai_service.openai_service.analyze_query_message') as mock_analyze_query, \
         patch('services.calendar_service.calendar_service.list_events') as mock_list_events:
        
        mock_analyze_query.return_value = {"is_query": True, "query_type": "list_events", "date_range": "tomorrow"}
        mock_list_events.return_value = "Your events for tomorrow are..."

        result = await handle_idle_state("test_user", "what about tomorrow")
        
        mock_analyze_query.assert_called_once_with("what about tomorrow")
        mock_list_events.assert_called_once_with("tomorrow")
        assert result == "Your events for tomorrow are..."
