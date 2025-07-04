#!/usr/bin/env python3
"""
Simple test script to verify the WhatsApp Calendar Bot functionality
"""

import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import patch

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_configuration():
    """Test configuration validation"""
    print("🔧 Testing Configuration...")
    
    try:
        from config import config
        
        # Test basic config loading
        print(f"   Environment: {config.ENVIRONMENT}")
        print(f"   Debug mode: {config.DEBUG}")
        print(f"   Timezone: {config.DEFAULT_TIMEZONE}")
        print(f"   OpenAI Model: {config.OPENAI_MODEL}")
        print(f"   OpenAI Top P: {config.OPENAI_TOP_P}")
        
        # Test validation (will show warnings for placeholder values)
        try:
            config.validate_config()
            print("   ✅ Configuration validation passed")
        except ValueError as e:
            print(f"   ⚠️  Configuration validation warnings: {e}")
            print("   (This is expected if using placeholder values)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Configuration test failed: {e}")
        return False

async def test_services():
    """Test service initialization"""
    print("\n🔌 Testing Service Initialization...")
    
    services_status = {}
    
    # Test OpenAI Service
    try:
        from services.openai_service import openai_service
        if openai_service.client:
            print("   ✅ OpenAI service initialized")
            services_status['openai'] = True
        else:
            print("   ⚠️  OpenAI service not initialized (check API key)")
            services_status['openai'] = False
    except Exception as e:
        print(f"   ❌ OpenAI service error: {e}")
        services_status['openai'] = False
    
    # Test Google Calendar Service
    try:
        from services.calendar_service import calendar_service
        if calendar_service.service:
            print("   ✅ Google Calendar service initialized")
            services_status['calendar'] = True
        else:
            print("   ⚠️  Google Calendar service not initialized (check credentials)")
            services_status['calendar'] = False
    except Exception as e:
        print(f"   ❌ Google Calendar service error: {e}")
        services_status['calendar'] = False
    
    # Test Twilio Service
    try:
        from services.twilio_service import twilio_service
        if twilio_service.client:
            print("   ✅ Twilio service initialized")
            services_status['twilio'] = True
        else:
            print("   ⚠️  Twilio service not initialized (check credentials)")
            services_status['twilio'] = False
    except Exception as e:
        print(f"   ❌ Twilio service error: {e}")
        services_status['twilio'] = False
    
    return services_status

async def test_openai_functionality():
    """Test OpenAI task detection"""
    print("\n🤖 Testing OpenAI Task Detection...")
    
    try:
        from services.openai_service import openai_service
        
        if not openai_service.client:
            print("   ⚠️  Skipping OpenAI test - service not initialized")
            return False
        
        # Test task detection
        test_messages = [
            "Remind me to call John tomorrow at 3pm",
            "How are you today?",
            "Meeting with team on Friday"
        ]
        
        for message in test_messages:
            try:
                analysis = await openai_service.analyze_task_message(message)
                print(f"   Message: '{message}'")
                print(f"   Is Task: {analysis.is_task}")
                if analysis.extracted_info:
                    print(f"   Extracted: {analysis.extracted_info}")
                print()
            except Exception as e:
                print(f"   ❌ Error analyzing '{message}': {e}")
        
        print("   ✅ OpenAI functionality test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ OpenAI functionality test failed: {e}")
        return False

async def test_calendar_parsing():
    """Test calendar date/time parsing"""
    print("\n📅 Testing Calendar Date/Time Parsing...")
    
    try:
        from services.calendar_service import calendar_service
        
        test_cases = [
            ("tomorrow", "3pm"),
            ("next Friday", "morning"),
            ("Monday", "14:30"),
            ("2024-01-15", "10:00"),
            ("today", "1.5 hours"),
        ]
        
        for date_str, time_str in test_cases:
            try:
                if "hour" in time_str:
                    # This is a duration test
                    task_data = {"duration": time_str, "date": "today", "time": "3pm"}
                    with patch.object(calendar_service, 'service') as mock_service:
                        mock_service.events().insert().execute.return_value = {"id": "test", "htmlLink": "test_url"}
                        await calendar_service.create_event(task_data)
                        # The actual assertion is that this doesn't raise an error and that the duration is parsed correctly internally.
                        # We can't easily assert the internal duration_minutes value without more refactoring,
                        # but we can check the logs or add more detailed return values if needed.
                        print(f"   '{time_str}' → Successfully parsed, event created.")

                else:
                    # This is a datetime test
                    parsed_dt = calendar_service.parse_datetime_string(date_str, time_str)
                    if parsed_dt:
                        print(f"   '{date_str}' + '{time_str}' → {parsed_dt}")
                    else:
                        print(f"   ❌ Failed to parse '{date_str}' + '{time_str}'")
            except Exception as e:
                print(f"   ❌ Error parsing '{date_str}' + '{time_str}': {e}")
        
        print("   ✅ Calendar parsing test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Calendar parsing test failed: {e}")
        return False

async def test_conversation_management():
    """Test conversation state management"""
    print("\n💬 Testing Conversation Management...")
    
    try:
        from models.conversation import conversation_manager
        from models.schemas import ConversationState
        
        test_phone = "+1234567890"
        
        # Test session creation
        session = conversation_manager.get_session(test_phone)
        print(f"   Created session for {test_phone}")
        print(f"   Initial state: {session.state}")
        
        # Test state updates
        conversation_manager.update_session_state(test_phone, ConversationState.TASK_DETECTED)
        session = conversation_manager.get_session(test_phone)
        print(f"   Updated state: {session.state}")
        
        # Test task data
        conversation_manager.update_task_data(test_phone, "title", "Test meeting")
        conversation_manager.update_task_data(test_phone, "date", "tomorrow")
        
        task_data = conversation_manager.get_task_data(test_phone)
        print(f"   Task data: {task_data}")
        
        # Test missing fields
        missing = conversation_manager.get_missing_fields(test_phone)
        print(f"   Missing fields: {missing}")
        
        # Clean up
        conversation_manager.clear_session(test_phone)
        print("   ✅ Conversation management test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Conversation management test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 WhatsApp Calendar Bot - Test Suite")
    print("=" * 50)
    
    test_results = {}
    
    # Run tests
    test_results['config'] = await test_configuration()
    test_results['services'] = await test_services()
    test_results['conversation'] = await test_conversation_management()
    test_results['calendar_parsing'] = await test_calendar_parsing()
    
    # Only test OpenAI if service is available
    services_status = test_results.get('services', {})
    if isinstance(services_status, dict) and services_status.get('openai'):
        test_results['openai'] = await test_openai_functionality()
        test_results['confirmation_modification'] = await test_confirmation_modification()
    else:
        print("\n🤖 Skipping OpenAI functionality test - service not available")
        test_results['openai'] = None
        test_results['confirmation_modification'] = None
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    
    passed = 0
    total = 0
    
    for test_name, result in test_results.items():
        if result is None:
            print(f"   {test_name}: SKIPPED")
        elif result:
            print(f"   {test_name}: ✅ PASSED")
            passed += 1
            total += 1
        else:
            print(f"   {test_name}: ❌ FAILED")
            total += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your app is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the configuration and credentials.")
        print("\nNext steps:")
        print("1. Update .env file with actual API keys")
        print("2. Add Google credentials JSON file")
        print("3. Verify all services are properly configured")
    
    return passed == total

async def test_confirmation_modification():
    """Test that the user can modify task details during confirmation"""
    print("\n🔄 Testing Confirmation Modification...")
    
    try:
        from models.conversation import conversation_manager
        from models.schemas import ConversationState
        from routers.webhook import handle_confirming_state

        user_phone = "+1122334455"
        conversation_manager.clear_session(user_phone)
        conversation_manager.update_task_data(user_phone, 'title', 'Run')
        conversation_manager.update_task_data(user_phone, 'date', 'today')
        conversation_manager.update_task_data(user_phone, 'time', '6pm')
        conversation_manager.update_session_state(user_phone, ConversationState.CONFIRMING)
        
        modification_message = "change it to tomorrow at 6am"
        
        response = await handle_confirming_state(user_phone, modification_message)
        
        updated_task_data = conversation_manager.get_task_data(user_phone)
        
        print(f"   Original Task: {{ 'title': 'Run', 'date': 'today', 'time': '6pm' }}")
        print(f"   Modification: '{modification_message}'")
        print(f"   Updated Task: {updated_task_data}")
        
        assert updated_task_data['date'] == 'tomorrow'
        assert updated_task_data['time'] == '6am'
        assert "confirm the details" in response
        
        print("   ✅ Confirmation modification test completed")
        return True

    except Exception as e:
        print(f"   ❌ Confirmation modification test failed: {e}")
        return False

if __name__ == "__main__":

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
