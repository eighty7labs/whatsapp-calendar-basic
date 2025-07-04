# WhatsApp Google Calendar Bot

A WhatsApp bot that intelligently detects tasks and appointments from messages and automatically adds them to your Google Calendar using AI-powered natural language processing.

## Features

- 🤖 **AI-Powered Task Detection**: Uses OpenAI to intelligently identify tasks and appointments from natural language
- 📅 **Google Calendar Integration**: Automatically creates calendar events with proper timezone handling
- 💬 **WhatsApp Interface**: Easy-to-use WhatsApp bot interface via Twilio
- 🔄 **Conversation Management**: Maintains context across messages to collect missing information
- 🌍 **Natural Language Processing**: Supports various date/time formats and natural language expressions
- ✏️ **Event Editing**: Edit existing events directly through WhatsApp chat
- 🛡️ **Error Handling**: Robust error handling with retry logic and graceful degradation
- 📊 **Logging & Monitoring**: Comprehensive logging and health check endpoints

## Architecture

```
WhatsApp Message → Twilio → FastAPI Webhook → OpenAI Analysis → Google Calendar
```

## Prerequisites

1. **Twilio Account** with WhatsApp Business API access
2. **OpenAI API Key** (GPT-4 or GPT-3.5-turbo)
3. **Google Cloud Project** with Calendar API enabled
4. **Python 3.8+**

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd whatsapp_google_calendar
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the `.env` file and update with your actual credentials:

```bash
cp .env .env.local
```

Update `.env` with your actual values:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_actual_twilio_account_sid
TWILIO_AUTH_TOKEN=your_actual_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# OpenAI Configuration
OPENAI_API_KEY=your_actual_openai_api_key
OPENAI_MODEL=gpt-4.1-mini

# Google Calendar Configuration
GOOGLE_CALENDAR_ID=your_google_calendar_id@gmail.com
GOOGLE_CREDENTIALS_PATH=credentials/google_credentials.json

# Application Configuration
SECRET_KEY=your-secure-secret-key
ENVIRONMENT=development
DEBUG=True
DEFAULT_TIMEZONE=Asia/Calcutta
```

### 3. Google Calendar Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Calendar API
4. Create a Service Account:
   - Go to IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Download the JSON key file
   - Save it as `credentials/google_credentials.json`
5. Share your Google Calendar with the service account email
6. Get your Calendar ID from Google Calendar settings

### 4. Twilio WhatsApp Setup

1. Create a [Twilio account](https://www.twilio.com/)
2. Set up WhatsApp Business API (Twilio Sandbox for testing)
3. Configure webhook URL: `https://your-domain.com/webhook/whatsapp`
4. Note your Account SID, Auth Token, and WhatsApp number

### 5. OpenAI Setup

1. Create an [OpenAI account](https://platform.openai.com/)
2. Generate an API key
3. Ensure you have sufficient credits/quota

## Running the Application

### Development

```bash
python main.py
```

The application will start on `http://localhost:8000`

### Production (Heroku)

```bash
git add .
git commit -m "Deploy WhatsApp Calendar Bot"
git push heroku main
```

## Usage Examples

Send these messages to your WhatsApp bot:

### Basic Task Scheduling
- "Remind me to call John tomorrow at 3pm"
- "Meeting with team on Friday at 2pm"
- "Doctor appointment next Tuesday at 10am"

### Natural Language Support
- "Lunch with Sarah on Monday"
- "Gym session tomorrow morning"
- "Call mom this evening"
- "Team standup next Friday at 9am"

### Event Editing (NEW!)
- "Change my meeting time to 4pm"
- "Update the title to Sprint Planning"
- "Make the duration 2 hours"
- "Reschedule the team meeting to tomorrow"
- "Edit my last event"

### Commands
- `help` - Show help message
- `cancel` - Cancel current operation

## API Endpoints

- `GET /` - Root endpoint with status
- `GET /health` - Detailed health check
- `POST /webhook/whatsapp` - Twilio webhook endpoint

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | Required |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | Required |
| `TWILIO_WHATSAPP_NUMBER` | Twilio WhatsApp number | `whatsapp:+14155238886` |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o-mini` |
| `OPENAI_TOP_P` | OpenAI top_p value | `0.2` |
| `GOOGLE_CALENDAR_ID` | Google Calendar ID | Required |
| `GOOGLE_CREDENTIALS_PATH` | Path to Google credentials JSON | `credentials/google_credentials.json` |
| `DEFAULT_TIMEZONE` | Default timezone | `Asia/Calcutta` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENVIRONMENT` | Environment (development/production) | `development` |

### Supported Date/Time Formats

**Dates:**
- Relative: today, tomorrow, day after tomorrow
- Weekdays: Monday, Tuesday, next Friday
- Specific: 2024-01-15, 15/01/2024, January 15
- Ordinal: 15th, 1st, 22nd

**Times:**
- 12-hour: 3pm, 10:30am, 2 PM
- 24-hour: 15:00, 14:30
- Natural: morning, afternoon, evening, noon

## Troubleshooting

### Common Issues

#### 1. Configuration Validation Errors
```
ValueError: Placeholder values detected for: OPENAI_API_KEY
```
**Solution**: Update `.env` file with actual API keys, not placeholder values.

#### 2. Google Calendar Service Not Initialized
```
Google Calendar service not initialized
```
**Solutions**:
- Ensure `credentials/google_credentials.json` exists
- Verify the service account has Calendar API access
- Check that your calendar is shared with the service account email

#### 3. OpenAI API Errors
```
OpenAI API failed after 3 attempts
```
**Solutions**:
- Verify your OpenAI API key is valid
- Check your OpenAI account has sufficient credits
- Ensure you have access to the specified model

#### 4. Twilio Webhook Issues
```
Twilio error 400: Bad request
```
**Solutions**:
- Verify Twilio credentials are correct
- Check webhook URL is accessible from internet
- Ensure WhatsApp number format is correct

### Health Check

Visit `/health` endpoint to check service status:

```json
{
  "status": "healthy",
  "services": {
    "openai": "connected",
    "google_calendar": "connected",
    "twilio": "connected"
  }
}
```

### Logs

Application logs include:
- Incoming message details
- Processing time for each request
- Service connection status
- Error details with stack traces

## Development

### Project Structure

```
whatsapp_google_calendar/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── models/
│   ├── schemas.py         # Pydantic models
│   └── conversation.py    # Conversation state management
├── services/
│   ├── openai_service.py  # OpenAI API integration
│   ├── calendar_service.py # Google Calendar API
│   └── twilio_service.py  # Twilio WhatsApp API
├── routers/
│   └── webhook.py         # Webhook endpoints
├── utils/
│   └── helpers.py         # Utility functions
└── credentials/
    └── google_credentials.json # Google service account key
```

### Adding New Features

1. **New Conversation States**: Add to `ConversationState` enum in `models/schemas.py`
2. **Enhanced NLP**: Modify prompts in `services/openai_service.py`
3. **Calendar Features**: Extend `services/calendar_service.py`
4. **Message Handling**: Update handlers in `routers/webhook.py`

## Security Considerations

- Store sensitive credentials in environment variables
- Use webhook signature validation in production
- Implement rate limiting for API endpoints
- Regular security updates for dependencies
- Monitor logs for suspicious activity

## Performance Optimization

- Use Redis for session storage in production
- Implement connection pooling for external APIs
- Add caching for frequently accessed data
- Monitor and optimize API response times
- Use async/await patterns throughout

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review application logs
3. Test individual service connections via `/health` endpoint
4. Create an issue with detailed error information

## Changelog

### v1.1.0 (Latest)
- ✨ **NEW: Event Editing Functionality**
  - Edit event titles, times, durations, and dates through WhatsApp
  - Smart event detection and selection
  - Natural language edit commands
  - Multi-event selection when ambiguous
- 🔧 Enhanced OpenAI prompts for better edit detection
- 📊 Improved conversation state management
- 🛠️ Extended Google Calendar service with update methods
- 🧪 Comprehensive test suite for edit functionality

### v1.0.0
- Initial release with core functionality
- AI-powered task detection
- Google Calendar integration
- WhatsApp interface via Twilio
- Comprehensive error handling and logging
