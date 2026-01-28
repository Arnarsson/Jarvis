# Meeting Brief API - Testing Guide

## Endpoint
`GET /api/meeting/{event_id}/brief`

## Test the API

### 1. Start the server
```bash
cd server
python -m jarvis_server.main
```

### 2. Test with curl
```bash
# Replace {event_id} with an actual calendar event ID from your database
curl -X GET "http://localhost:8000/api/meeting/{event_id}/brief?lookback_days=30" \
  -H "accept: application/json"
```

### 3. Expected Response Structure
```json
{
  "meeting": {
    "title": "Thomas Sync",
    "start_time": "2026-01-28T15:00:00Z",
    "attendees": ["thomas@example.com"],
    "location": "Zoom link"
  },
  "context": {
    "last_touchpoints": [
      {
        "type": "email",
        "date": "2026-01-25",
        "summary": "Discussed pricing proposal",
        "snippet": "Thanks for the call...",
        "source_id": "email_123"
      }
    ],
    "open_loops": [
      {
        "description": "Send pricing doc",
        "owner": "you",
        "due_date": "2026-01-20",
        "status": "overdue",
        "source": "email_123"
      }
    ],
    "shared_files": []
  },
  "suggested_talking_points": [
    "Follow up on overdue pricing doc",
    "Discuss Q1 timeline"
  ],
  "why": {
    "reasons": ["Meeting in 45 minutes", "1 overdue commitment"],
    "confidence": 0.85,
    "sources": ["email_123", "promise_456"]
  }
}
```

## Data Sources Queried

The API aggregates data from:
1. **Calendar API** - Meeting details + attendees
2. **Email threads** - Last 30 days of emails with attendees
3. **Captures** - Activity mentions of attendee names
4. **Promises** - Open commitments/tasks tagged to attendees

## Implementation Notes

### Response Structure
- **meeting**: Basic meeting metadata (title, time, attendees, location)
- **context**: Rich contextual data
  - `last_touchpoints`: Recent interactions (emails, captures)
  - `open_loops`: Pending/overdue commitments
  - `shared_files`: Shared documents (placeholder for future)
- **suggested_talking_points**: AI-generated discussion topics
- **why**: Explanation of urgency and relevance
  - `reasons`: Plain English reasons (e.g., "Meeting in 45 minutes")
  - `confidence`: 0-1 score
  - `sources`: IDs of source data

### Query Parameters
- `lookback_days` (default: 30, range: 1-90): How far back to search for touchpoints

### Status Codes
- `200`: Success
- `404`: Meeting not found
- `500`: Internal server error

## Integration with Frontend

The dashboard should call this endpoint:
1. **10 minutes before meeting**: Show prep card in Command Center
2. **One-tap access**: "Prep in 60s" button opens brief
3. **Action buttons**: 
   - Draft email (based on context)
   - Create tasks (from open loops)
   - View sources (drill-down to emails/captures)

## Future Enhancements
- [ ] Implement shared files tracking from Google Drive/captures
- [ ] Add LLM-powered talking point generation
- [ ] Cache briefs for 5 minutes to reduce DB load
- [ ] Add meeting prep notifications
- [ ] Track brief open rate (metrics)
