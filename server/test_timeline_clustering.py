#!/usr/bin/env python3
"""Test script for timeline clustering functionality."""

from datetime import datetime, timedelta
from typing import Optional


class MockCapture:
    """Mock Capture for testing."""
    
    def __init__(self, id: str, timestamp: datetime, ocr_text: Optional[str]):
        self.id = id
        self.timestamp = timestamp
        self.ocr_text = ocr_text


def test_clustering():
    """Test basic clustering logic."""
    # Import the functions
    import sys
    sys.path.insert(0, 'src')
    from jarvis_server.api.timeline import (
        cluster_captures_into_sessions,
        extract_app_from_ocr,
        extract_project_from_ocr,
        generate_summary_from_ocr,
    )
    
    # Test app extraction
    print("Testing app extraction:")
    print(f"  VS Code: {extract_app_from_ocr('Welcome to VS Code - main.py')}")
    print(f"  Chrome: {extract_app_from_ocr('Google Chrome - Gmail')}")
    print(f"  Slack: {extract_app_from_ocr('Slack - #general')}")
    print(f"  Unknown: {extract_app_from_ocr('Some random text')}")
    print()
    
    # Test project extraction
    print("Testing project extraction:")
    print(f"  Path: {extract_project_from_ocr('/home/user/RecruitOS/main.py')}")
    print(f"  Title: {extract_project_from_ocr('JarvisApp - VS Code')}")
    print()
    
    # Test clustering with mock data
    base_time = datetime.now()
    
    # Create mock captures: 2 VS Code sessions with 5-minute gap
    captures = [
        # Session 1: VS Code (3 captures, 2 minutes apart)
        MockCapture("cap_1", base_time, "VS Code - main.py working on app.py"),
        MockCapture("cap_2", base_time + timedelta(minutes=2), "VS Code - app.py def process_data"),
        MockCapture("cap_3", base_time + timedelta(minutes=4), "VS Code - utils.py class Helper"),
        
        # 6-minute gap -> should split session
        
        # Session 2: Chrome (2 captures, 1 minute apart)
        MockCapture("cap_4", base_time + timedelta(minutes=10), "Chrome - Gmail inbox"),
        MockCapture("cap_5", base_time + timedelta(minutes=11), "Chrome - Gmail compose"),
    ]
    
    # Reverse to simulate DESC order from DB
    captures_desc = list(reversed(captures))
    
    print("Testing clustering:")
    sessions = cluster_captures_into_sessions(captures_desc)
    
    print(f"  Total sessions: {len(sessions)}")
    for i, session in enumerate(sessions):
        print(f"\n  Session {i + 1}:")
        print(f"    ID: {session.id}")
        print(f"    App: {session.primary_app}")
        print(f"    Duration: {session.duration_minutes} min")
        print(f"    Captures: {session.capture_count}")
        print(f"    Summary: {session.summary}")
        print(f"    Time range: {session.start_time.strftime('%H:%M')} - {session.end_time.strftime('%H:%M')}")
    
    print("\n✅ Clustering test completed!")


if __name__ == "__main__":
    test_clustering()
