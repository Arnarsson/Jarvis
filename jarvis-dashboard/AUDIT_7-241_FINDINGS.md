# Action Buttons Audit — Issue 7-241

## Audit Date
$(date)

## Summary
Audited all dashboard components for presence of actionable buttons.

## Components WITH Adequate Action Buttons ✓
1. **CommandCenter.tsx**
   - ResumeCard: "Resume Workspace", "View Brief", "Wrong → Choose" buttons ✓
   - NextMeetingSection: "Prep in 60s" button ✓
   - FocusInboxSection: "Open Triage →" button ✓

2. **MeetingBrief.tsx**
   - Quick Actions: "Draft Email", "Open Last Doc", "Create Tasks" buttons ✓
   - MeetingBriefButton: "Prep" button ✓

3. **ProactiveActions.tsx**
   - Each suggestion has action buttons: "HANDLE NOW", "DRAFT MESSAGE", "REACH OUT", "REVIEW", "DRAFT REPLY", "CREATE TASK", "ACT ON IT" ✓

4. **WhatShouldIDo.tsx**
   - Comprehensive action buttons: "CREATE TASK", "DONE", "START" ✓
   - Custom ActionButton component with loading states ✓

## Components MISSING Action Buttons ❌

### HIGH PRIORITY

1. **PendingDecisions.tsx** ❌
   - **Issue**: Decision cards are clickable to expand but have NO action buttons
   - **Needed**: "Reply", "Approve", "Decline", "Snooze", "Mark Read" buttons
   - **Impact**: HIGH - decisions require action

2. **AgendaList.tsx** ❌
   - **Issue**: Meeting events expand on click but lack explicit action buttons
   - **Needed**: "Join Meeting", "Prep Brief", "Reschedule", "Skip" buttons
   - **Impact**: MEDIUM - meetings need quick actions

3. **OpenLoopsSection (in CommandCenter.tsx)** ⚠️
   - **Issue**: Only has "View All →" link, individual loop items lack actions
   - **Needed**: "Mark Done", "Remind", "Snooze" buttons per item
   - **Impact**: MEDIUM - open loops need closure actions

### MEDIUM PRIORITY

4. **WhereYouLeftOff.tsx** ⚠️
   - **Issue**: Entire cards are links but no explicit "Resume" button
   - **Enhancement**: Add "Resume" button for clearer affordance
   - **Impact**: LOW - navigation works but UX could be clearer

5. **ProjectPulse.tsx** ⚠️
   - **Issue**: Project cards open modal on click, but no explicit action buttons
   - **Enhancement**: Add "View Details", "Resume", "Update" buttons per project
   - **Impact**: LOW - clickability works but explicit buttons better

6. **Todays3Section (in CommandCenter.tsx)** ⚠️
   - **Issue**: Has "+ Add" link but individual items lack action buttons
   - **Enhancement**: Add "Mark Done", "Edit", "Delete" buttons per item
   - **Impact**: LOW - items already show done state, but inline actions would help

## Recommendations

### Phase 1: Critical Fixes
1. Add action buttons to **PendingDecisions.tsx** (Reply, Approve, Decline)
2. Add action buttons to **AgendaList.tsx** meeting rows (Join, Prep, Skip)

### Phase 2: Enhancements
3. Add item-level actions to **OpenLoopsSection** (Mark Done, Remind, Snooze)
4. Add explicit Resume button to **WhereYouLeftOff.tsx** cards
5. Add action buttons to **ProjectPulse.tsx** cards (View, Resume, Update)

### Phase 3: Polish
6. Add item-level actions to **Todays3Section** (Mark Done inline)

## Action Plan
- Start with PendingDecisions.tsx (highest impact)
- Then AgendaList.tsx
- Build/test after each change
- Commit incrementally
