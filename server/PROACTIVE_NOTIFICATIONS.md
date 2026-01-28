# Proactive Notifications Feature

## Overview

This feature enables Jarvis to proactively push critical insights to Telegram, helping you stay on top of relationships and follow-ups without manual checking.

## What It Does

The system periodically analyzes your conversation data to detect patterns like:
- **Follow-up opportunities**: People you haven't contacted in 5+ days but usually talk to regularly
- Priority-based notifications (high priority = notification sound, lower = silent)

## Architecture

### Components

1. **Notification System** (`jarvis_server/notifications/`)
   - `telegram.py` - Sends messages via Clawdbot's Telegram integration
   - `insights.py` - Detects patterns and generates actionable insights
   - `tasks.py` - Background task orchestration and state management

2. **API Endpoint** (`jarvis_server/api/insights.py`)
   - `GET /api/v2/insights` - Preview current insights without sending
   - `POST /api/v2/insights/notify` - Manually trigger notification check

3. **Worker Integration** (`jarvis_server/processing/worker.py`)
   - Cron job runs 3x daily (9am, 3pm, 9pm)
   - Automatic deduplication prevents spam
   - 4-hour minimum between runs

## How It Works

### Follow-up Detection Algorithm

```sql
1. Analyze conversations from last 60 days
2. Extract person names (capitalized names heuristic)
3. Calculate:
   - How often you talk (mention count)
   - When you last talked (recency)
   - Days since last contact
4. Flag if:
   - Regular contact (3+ mentions)
   - Haven't talked in 5-30 days
   - Not a false positive (Google, GitHub, etc.)
```

### Notification Logic

- **Max 3 insights per run** to avoid overwhelming you
- **Priority levels**:
  - 2 (High): 14+ days, notification sound
  - 1 (Medium): 7-14 days, silent
  - 0 (Low): 5-7 days, silent
- **Deduplication**: Tracks last 50 sent insights to prevent repeats

### State Management

State file: `/tmp/jarvis-notification-state.json`
```json
{
  "last_run": "2024-01-27T19:00:00Z",
  "sent_insights": ["Check in with Alice? (7 days)", ...]
}
```

## Usage

### API Testing

```bash
# Preview insights without sending
curl http://localhost:8000/api/v2/insights

# Manually trigger notification check
curl -X POST http://localhost:8000/api/v2/insights/notify
```

### Telegram Integration

Messages are sent via Clawdbot:
```bash
clawdbot message send --channel telegram --message "💡 Insight..."
```

Requires Clawdbot to be configured with Telegram credentials.

## Cron Schedule

```python
cron(check_and_notify, hour={9, 15, 21}, minute=0)
```

Runs at:
- 9:00 AM - Morning check
- 3:00 PM - Afternoon check
- 9:00 PM - Evening check

## Future Enhancements

Potential additional insights to implement:

- [ ] Upcoming meetings without agenda
- [ ] Promises/commitments due soon
- [ ] Patterns from screen captures (app usage)
- [ ] Important emails without response
- [ ] Calendar gaps suggesting available time
- [ ] Recurring topics requiring decisions

## Configuration

### Environment Variables

None required currently. Uses existing Jarvis configuration:
- Database (conversations table)
- Clawdbot CLI (for Telegram)

### Customization

Edit insight thresholds in `insights.py`:
```python
WHERE days_since_last >= 5  # Minimum gap
AND days_since_last <= 30   # Maximum gap
AND mention_count >= 3      # Regular contact threshold
```

## Deployment

The feature is automatically loaded when:
1. Docker containers are rebuilt
2. ARQ worker restarts
3. Cron schedule activates

No manual intervention needed after deployment.

## Troubleshooting

### No insights detected
- Check if conversations exist in database
- Verify conversation dates are recent (<60 days)
- Ensure source includes telegram/whatsapp/slack

### Notifications not sending
- Check Clawdbot is configured: `clawdbot message send --help`
- Verify Telegram credentials in Clawdbot config
- Check worker logs: `docker logs jarvis-worker`

### Duplicate notifications
- State file should track sent insights
- If duplicates persist, check `/tmp/jarvis-notification-state.json`
- Worker may need restart to reload state

## Testing

Run insights detection without sending:
```bash
# In Jarvis server container or venv
python -c "
import asyncio
from jarvis_server.notifications.insights import detect_all_insights

async def test():
    insights = await detect_all_insights()
    for i in insights:
        print(f'[P{i.priority}] {i.message}')

asyncio.run(test())
"
```

## Linear Issue

- Issue: 7-244 "Jarvis → Telegram proactive push"
- Status: ✅ Implemented
- Next: Monitor effectiveness and add more insight types
