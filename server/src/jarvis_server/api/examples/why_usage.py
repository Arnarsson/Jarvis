"""Example usage of Why + Confidence plumbing.

This demonstrates how to use the WhyPayload data contract
and helper functions in your own endpoints.
"""

from datetime import datetime, timezone

from jarvis_server.api.helpers import (
    build_why_from_calendar,
    build_why_from_capture,
    build_why_from_conversation,
    build_why_from_email,
    build_why_from_pattern,
    build_why_payload,
    merge_why_payloads,
)
from jarvis_server.api.models import Source, WhyPayload


def example_email_suggestion():
    """Example: Building WhyPayload for an email suggestion."""
    why = build_why_from_email(
        email_id="msg_12345",
        email_snippet="Hi Sven, can you send the proposal by Friday? Thanks!",
        email_timestamp=datetime.now(timezone.utc),
        reasons=[
            "Sender is VIP contact",
            "Email contains deadline mention",
            "Related to active project"
        ],
        confidence=0.85,
        additional_sources=[
            {
                "type": "calendar",
                "id": "evt_789",
                "timestamp": datetime.now(timezone.utc),
                "snippet": "Project Review Meeting - Friday 3pm",
                "url": "/calendar?event=evt_789"
            }
        ]
    )
    
    return why


def example_pattern_suggestion():
    """Example: Building WhyPayload for a detected pattern."""
    why = build_why_from_pattern(
        pattern_id="pat_abc123",
        pattern_description="You typically review email at 9am and 4pm",
        pattern_last_seen=datetime.now(timezone.utc),
        reasons=[
            "Detected 15 times over past month",
            "Pattern type: Time Habit",
            "Suggested action available"
        ],
        confidence=0.92,
        source_conversation_ids=["conv_1", "conv_2", "conv_3"]
    )
    
    return why


def example_meeting_brief():
    """Example: Building WhyPayload for a meeting brief suggestion."""
    # Manual construction
    sources = [
        Source(
            type="calendar",
            id="evt_555",
            timestamp=datetime.now(timezone.utc),
            snippet="Weekly Sync with Thomas",
            url="/calendar?event=evt_555"
        ),
        Source(
            type="email",
            id="msg_777",
            timestamp=datetime.now(timezone.utc),
            snippet="Thomas: I have some updates on the Atlas project...",
            url="/email/msg_777"
        )
    ]
    
    why = WhyPayload(
        reasons=[
            "Meeting starts in 10 minutes",
            "3 open action items from last meeting",
            "Recent email exchange with attendee"
        ],
        confidence=0.95,
        sources=sources
    )
    
    return why


def example_merged_suggestions():
    """Example: Merging multiple WhyPayloads into one comprehensive explanation."""
    
    # Email-based suggestion
    email_why = build_why_from_email(
        email_id="msg_100",
        email_snippet="Follow up on Q1 planning",
        email_timestamp=datetime.now(timezone.utc),
        reasons=["Important email from manager"],
        confidence=0.8
    )
    
    # Calendar-based suggestion
    calendar_why = build_why_from_calendar(
        event_id="evt_200",
        event_title="Q1 Planning Review",
        event_start=datetime.now(timezone.utc),
        reasons=["Meeting scheduled for today"],
        confidence=0.9
    )
    
    # Merge both
    merged = merge_why_payloads([email_why, calendar_why])
    
    # Result will have:
    # - reasons from both sources
    # - confidence = min(0.8, 0.9) = 0.8
    # - sources from both
    
    return merged


def example_custom_payload():
    """Example: Building WhyPayload with custom logic."""
    sources = [
        {
            "type": "capture",
            "id": "cap_999",
            "timestamp": datetime.now(timezone.utc),
            "snippet": "VS Code open with 5 uncommitted files",
            "url": "/timeline?capture=cap_999"
        },
        {
            "type": "conversation",
            "id": "conv_888",
            "timestamp": datetime.now(timezone.utc),
            "snippet": "Discussion about shipping this feature",
            "url": "/search?conversation=conv_888"
        }
    ]
    
    why = build_why_payload(
        reasons=[
            "Work in progress detected",
            "Related to sprint goal",
            "Discussed in recent conversation"
        ],
        confidence=0.75,
        sources=sources
    )
    
    return why


if __name__ == "__main__":
    # Run examples
    print("=== Email Suggestion ===")
    print(example_email_suggestion().model_dump_json(indent=2))
    
    print("\n=== Pattern Suggestion ===")
    print(example_pattern_suggestion().model_dump_json(indent=2))
    
    print("\n=== Meeting Brief ===")
    print(example_meeting_brief().model_dump_json(indent=2))
    
    print("\n=== Merged Suggestions ===")
    print(example_merged_suggestions().model_dump_json(indent=2))
    
    print("\n=== Custom Payload ===")
    print(example_custom_payload().model_dump_json(indent=2))
