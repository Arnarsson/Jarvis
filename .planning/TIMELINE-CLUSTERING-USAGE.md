# Timeline Session Clustering — Implementation Guide

**Issue:** 7-299 (P1 Quick Win)  
**Status:** ✅ Completed & Committed to master  
**Commit:** a1caa4a

---

## Overview

Timeline now supports **session clustering** to collapse hundreds of screenshots into readable, meaningful sessions. Instead of showing "450 captures in VS Code", the UI can now display "12 VS Code sessions" with smart summaries.

---

## API Usage

### Endpoint: `GET /api/timeline`

**New Parameter:**
- `grouped` (boolean, default: false) — Enable session clustering

### Example Requests

**Ungrouped (original behavior):**
```bash
GET /api/timeline?limit=50
```

**Grouped (new feature):**
```bash
GET /api/timeline?grouped=true&limit=50
```

### Response Format

**When `grouped=false` (default):**
```json
{
  "captures": [
    {
      "id": "cap_123",
      "timestamp": "2026-01-28T09:00:00Z",
      "filepath": "/path/to/screenshot.png",
      "width": 1920,
      "height": 1080,
      "monitor_index": 0,
      "has_ocr": true,
      "text_preview": "VS Code - main.py..."
    }
  ],
  "total": 450,
  "next_cursor": "2026-01-28T08:50:00Z",
  "has_more": true
}
```

**When `grouped=true`:**
```json
{
  "sessions": [
    {
      "id": "session_0_1738051200",
      "start_time": "2026-01-28T09:00:00Z",
      "end_time": "2026-01-28T11:30:00Z",
      "duration_minutes": 150,
      "primary_app": "VS Code",
      "project": "RecruitOS",
      "summary": "Working on app.py, utils.py • Topics: export, function, class",
      "capture_count": 45,
      "thumbnail_id": "cap_456",
      "captures": ["cap_1", "cap_2", "cap_3", ...]
    }
  ],
  "total_sessions": 12,
  "total_captures": 450,
  "next_cursor": "2026-01-28T08:45:00Z",
  "has_more": true
}
```

---

## Clustering Algorithm

### Session Boundaries

A new session is created when:
1. **Time gap > 5 minutes** between captures
2. **App changes** (e.g., VS Code → Chrome)
   - Exception: "Unknown" app doesn't trigger split

### App Detection

Detects 15+ common applications from OCR text:
- **Dev Tools:** VS Code, PyCharm, IntelliJ, GitHub
- **Browsers:** Chrome, Firefox
- **Communication:** Slack, Discord, Gmail
- **Productivity:** Notion, Linear, Jira, Figma
- **System:** Terminal
- **Media:** Spotify

Pattern matching uses case-insensitive regex on OCR text.

### Project Detection

Extracts project names from:
- **File paths:** `/home/user/RecruitOS/main.py` → "RecruitOS"
- **Window titles:** `JarvisApp - VS Code` → "JarvisApp"

### Summary Generation

Smart summary from OCR text:
1. **File references:** Extracts `.py`, `.js`, `.ts`, `.md`, etc.
2. **Common words:** Filters stop words, counts frequency
3. **Format:** "Working on {files} • Topics: {keywords}"

Example summaries:
- `"Working on app.py, utils.py • Topics: export, function, class"`
- `"Topics: gmail, inbox, compose"`
- `"Activity detected"` (fallback)

### Thumbnail Selection

Uses **middle capture** as representative thumbnail (better than first/last).

---

## Frontend Integration

### Display Sessions as Cards

```tsx
interface Session {
  id: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  primary_app: string;
  project?: string;
  summary: string;
  capture_count: number;
  thumbnail_id: string;
  captures: string[];
}

function SessionCard({ session }: { session: Session }) {
  return (
    <div className="session-card">
      <img src={`/api/captures/${session.thumbnail_id}/image`} />
      <div className="session-info">
        <h3>{session.primary_app} {session.project && `— ${session.project}`}</h3>
        <p>{session.summary}</p>
        <div className="session-meta">
          {formatDuration(session.duration_minutes)} • {session.capture_count} captures
        </div>
      </div>
      <button onClick={() => expandSession(session.captures)}>
        Expand →
      </button>
    </div>
  );
}
```

### Expand Session

When user clicks "Expand", fetch individual captures:
```tsx
const expandSession = async (captureIds: string[]) => {
  // Fetch captures from original endpoint
  const captures = await Promise.all(
    captureIds.map(id => fetch(`/api/timeline/${id}`))
  );
  // Display in modal or detail view
};
```

---

## Configuration

### Gap Threshold

Currently hardcoded to **5 minutes**. Can be made configurable via query param:

```python
# Future enhancement:
@router.get("/")
async def get_timeline(
    ...
    gap_minutes: int = Query(default=5, ge=1, le=60),
    ...
):
    sessions = cluster_captures_into_sessions(
        captures, 
        gap_threshold_minutes=gap_minutes
    )
```

### Custom App Patterns

Add new apps by editing `extract_app_from_ocr()`:

```python
app_patterns = [
    (r'\bvscode\b', "VS Code"),
    (r'\byour_app\b', "Your App"),  # ← Add here
    ...
]
```

---

## Testing

### Unit Test

Run the included test script:
```bash
cd ~/Documents/jarvis/server
python test_timeline_clustering.py
```

Expected output:
```
Testing app extraction:
  VS Code: VS Code
  Chrome: Chrome
  Slack: Slack
  Unknown: Unknown

Testing project extraction:
  Path: RecruitOS
  Title: JarvisApp

Testing clustering:
  Total sessions: 2

  Session 1:
    ID: session_1_1769627813
    App: Chrome
    Duration: 1 min
    Captures: 2
    Summary: Topics: chrome, gmail, inbox
    ...

✅ Clustering test completed!
```

### API Test

```bash
# Test grouped endpoint
curl "http://localhost:8000/api/timeline?grouped=true&limit=10" | jq '.sessions[0]'

# Verify backward compatibility (ungrouped)
curl "http://localhost:8000/api/timeline?limit=10" | jq '.captures[0]'
```

---

## Performance Considerations

### Fetch Limit

- **Ungrouped mode:** Fetches `limit + 1` captures (efficient)
- **Grouped mode:** Fetches **500 captures** to ensure proper clustering
  - Reason: Sessions can span many captures; need lookahead
  - Trade-off: More memory but better session accuracy

### Optimization Opportunities

1. **Pagination cursor improvement:** Use session boundary timestamps
2. **Caching:** Cache clustered sessions for frequent date ranges
3. **Incremental clustering:** Only cluster new captures since last fetch
4. **Database-level grouping:** Pre-compute sessions in background worker

---

## Definition of Done ✅

- [x] Timeline endpoint supports `?grouped=true`
- [x] Returns sessions with duration + app + summary
- [x] Sessions are expandable (capture IDs included)
- [x] Summary shows meaningful info (files, topics)
- [x] Committed to master (commit a1caa4a)

---

## Next Steps (Future Enhancements)

### Frontend Implementation
- [ ] Update timeline UI to show sessions by default
- [ ] Add "Expand session" interaction
- [ ] Show session duration as progress bars
- [ ] Filter by app type ("Show only VS Code sessions")

### Backend Improvements
- [ ] Configurable gap threshold via query param
- [ ] Pre-compute sessions in background worker
- [ ] Add window title extraction (from agent metadata)
- [ ] Machine learning for better app/project detection

### Analytics
- [ ] Track most common apps per day
- [ ] Detect "productive hours" based on app patterns
- [ ] Alert on unusual session patterns (too short/long)

---

## Contact

**Implemented by:** Mason (subagent)  
**Requester:** Sven  
**Date:** 2026-01-28  
**Linear Issue:** 7-299
