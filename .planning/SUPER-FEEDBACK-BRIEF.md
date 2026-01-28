# Jarvis "Super Feedback Brief" — Product Pivot

**Date:** 2026-01-28
**Author:** Sven
**Status:** STRATEGIC DIRECTION

---

## Executive Verdict

**Current state:** Data Librarian (great at ingesting + listing)
**Target state:** Executive Assistant (synthesizing + driving action)

**The pivot:** Passive Observation → Active Contextualization
- Resume, Prepare, Triage, Close loops
- Always with Why + Confidence + Undo

---

## Primary JTBD Outcomes

1. **Resume work fast** — 15 seconds to "I know what to do next"
2. **Don't miss commitments** — follow-ups become explicit tasks
3. **Show up prepared** — meeting brief is one tap with actions

---

## Core Metrics (Must Ship v1)

| Metric | Definition | Target |
|--------|------------|--------|
| Time-to-Context (TTC) | unlock → first meaningful action | <30s (P1), <15s (eventual) |
| Context Recovery Rate | % "Resume" used vs manual search | High |
| Meeting Readiness | opened pre-meeting brief before call | Binary |
| Triage Velocity | items processed/min in Focus Inbox | High |
| Stale Relationship Yield | reconnect → message within 24h | % |
| Inbound Noise Ratio | % auto-filtered without reading | >80% |
| Pattern Activation Rate | patterns → automation/project/task | % |

---

## Biggest UX Problems

### A) "Guilt UI" + Cognitive Overload
- "777 inbound" + raw timeline = panic + avoidance (especially ADHD)
- Counters don't answer: Now / Next / Later

### B) "So What?" Gap
- Insights like "Atlas is fading" are dead ends
- Need 1-click action: "Draft reconnection email", "Create follow-up task"

### C) Trust Gap (No Visible Why)
- Without "Why is this urgent?" + sources, users double-check raw data
- Time savings goes negative

---

## Product Pivot: New Mental Model

### Default Landing = Command Center (Flight Deck)

**Not** timeline or stats. Shows:
1. **RESUME** — where you left off
2. **TODAY'S 3** — set priorities in <20s
3. **OPEN LOOPS** — commitments + waiting-on
4. **NEXT MEETING** — prep brief
5. **FOCUS INBOX** — VIP triage

Timeline, Patterns, Search become drill-down tooling, not home.

---

## Designer Deliverables

### 1. Command Center Redesign
- Remove guilt stats ("00 tasks", "777 inbound")
- Replace with: Resume hero + Today's 3 + Open loops + Next meeting + Focus Inbox
- Include empty states + "first run" setup

### 2. "Why This Is Here" Trust Layer
Every suggestion needs:
- **Reason line** (plain English)
- **Confidence badge**
- **Sources drawer** ("Why panel") with snippets + timestamps

### 3. Comms "VIP Triage"
- Default: Priority (N) vs The Rest
- One-tap outcomes: Reply (draft) / Convert to task / Snooze / Archive
- Explain-why badge on Priority items

### 4. Meeting Brief UX
- 10 min before → card/notification
- Includes: last touchpoints, open loops, suggested agenda, files, actions

### 5. Actionable Patterns
Every pattern card has fixed actions:
- "Convert to Project"
- "Create Automation"
- "Ignore / Snooze"
- No read-only patterns

### Designer Definition of Done
3–5 screens fully specified with states:
- Command Center
- Search + Why panel
- Pre-meeting brief
- Comms triage
- Patterns → actions

Includes microcopy + interaction flows + error/empty/staleness states.

---

## Developer Deliverables

### 1. Context Resumption Engine (MVP)
Determine "last active project/thread" using:
- Last opened artifacts (doc/url/file)
- App context
- Recent comms

Output: "Resume [Project]" card with:
- Last decision
- Next action
- Links

### 2. Commitments Extraction → Confirmation Tray
Detect phrases: "I'll send / we need to / can you"
- Create "Detected commitments" inbox (confirm/edit)
- Becomes task with owner + due date

### 3. Inbox Segmentation Classifier
- Split into Priority vs Rest
- Start: simple rules + lightweight LLM on header/snippet
- Support bulk-archive of "Rest" with undo

### 4. Why + Confidence Plumbing
Every suggestion must attach:
- `reason: string[]`
- `confidence: number` (even rough heuristics)
- `sources: pointer[]` (message IDs, doc IDs, timestamps)

### 5. Timeline Clustering
- Collapse "450 captures in VS Code" into sessions
- Show session title + duration + expandable detail

### 6. Instrumentation (Non-negotiable)
Log events:
- open app, click resume, accept suggestion
- send message, convert to task, open brief
- dismiss notification, undo action

Emit all metrics above.

### Developer Definition of Done
- Resume works 70%+ subjectively (with feedback buttons)
- Priority inbox capped and actionable
- Commitments tray creates real tasks
- Every suggestion has Why + Confidence + at least 2 sources

---

## Prioritized Build Plan

### P0 (Week 1–2): Stop Anxiety + Create Daily Utility

| Deliverable | Acceptance Criteria |
|-------------|---------------------|
| Command Center home | No "777 inbound"; shows Resume + Today's 3 + Open loops + Next meeting + Focus Inbox |
| Focus Inbox | Priority list <25 items/day; "Rest" bulk-archive with undo |
| Why this is here | Every suggestion shows Reason line + confidence badge |
| Pre-meeting brief v1 | Open in 1 tap; includes last touchpoints + open loops + actions |

### P1 (Weeks 3–6): Make "Never Lose Context" Real

| Deliverable | Acceptance Criteria |
|-------------|---------------------|
| Resume engine v1 | Suggests correct thread/project ≥70% (via thumbs feedback) |
| Commitments extraction | 60%+ detected commitments editable + converted |
| Search upgrade | Top "AI synthesis" + sources grouped by system |

### P2 (Weeks 7–12): Trusted Automation + Delight

| Deliverable | Acceptance Criteria |
|-------------|---------------------|
| Actionable patterns | Every pattern has "Adopt / Convert / Ignore" |
| Automation center | Tiered approval; audit card every time |
| Daily wrap-up | EOD captures "first step tomorrow"; persists to Command Center |

---

## Screen Specs

### Command Center (Default)
```
┌─────────────────────────────────────────────────────┐
│  RESUME [Project Name]                              │
│  "Last active: 2h ago · 3 files open"               │
│  "Next step: Review PR from Thomas"                 │
│  [Resume Workspace] [View Brief] [Wrong → choose]   │
├─────────────────────────────────────────────────────┤
│  TODAY'S 3                    [+ Add]               │
│  □ Finish RecruitOS PDF export                      │
│  □ Review Atlas pricing proposal                    │
│  □ Prep for Thomas call                             │
├─────────────────────────────────────────────────────┤
│  OPEN LOOPS (5)                                     │
│  • Waiting on: Thomas pricing doc (3d overdue)      │
│  • Your commitment: Send Avnit proposal (due today) │
├─────────────────────────────────────────────────────┤
│  NEXT MEETING                                       │
│  "Thomas Sync" in 45 min [Prep in 60s]              │
├─────────────────────────────────────────────────────┤
│  FOCUS INBOX                                        │
│  Priority (4) · Rest (127 — auto-filtered)          │
│  [Open Triage]                                      │
└─────────────────────────────────────────────────────┘
```

### Search + Why Panel
- Top: AI synthesis
- Below: Sources grouped by app/system
- Right drawer: Why panel (snippets + timestamps + open-in-context)

### Comms Triage
- Tabs: Priority (N) | Rest (M)
- Buttons: Reply (draft) / Task / Snooze / Archive
- "Why priority": sender VIP, question detected, deadline mention, relationship stale

### Meeting Brief
- Recent context (last 3 touchpoints)
- Open loops (tasks + commitments)
- Suggested talking points
- Actions: Draft email, open last doc, create tasks

---

## Trust + Safety Requirements

1. Every suggestion: Reason + Confidence + Sources
2. Undo for bulk actions and automations ("Undo for 10 min" visible)
3. Audit log: what happened / why / what changed
4. Notification throttle: quiet hours, max/day, digest mode
5. Privacy controls: pause capture, app allowlist, "private mode"

---

## Handoff Checklist

### Designer Package
- [ ] Figma for 5 screens + states (empty/error/stale)
- [ ] Component inventory (cards, badges, drawers, action bars)
- [ ] Microcopy: Resume, Why line, Confidence, Undo, Priority reasons

### Dev Package
- [ ] Event schema + logging plan
- [ ] Data model: Project/Person/Meeting/Thread + link table
- [ ] "Why payload" contract: `{ reason[], confidence, sources[] }`
- [ ] Inbox classifier rules v1 + escalation to LLM v2
