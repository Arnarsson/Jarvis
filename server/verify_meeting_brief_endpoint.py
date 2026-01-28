#!/usr/bin/env python3
"""Verify that the meeting brief endpoint is properly registered."""

import sys
sys.path.insert(0, 'src')

from jarvis_server.main import create_app

def verify_endpoint():
    """Check that the meeting brief endpoint exists in the app routes."""
    app = create_app()
    
    # Get all routes
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append((route.path, route.methods, route.name))
    
    # Look for our endpoint
    target_path = "/api/meeting/{event_id}/brief"
    found = False
    
    print("Searching for meeting brief endpoint...")
    print(f"Target: GET {target_path}\n")
    
    for path, methods, name in routes:
        if "/api/meeting" in path or "brief" in path.lower():
            print(f"  {methods} {path} ({name})")
            if path == target_path and "GET" in methods:
                found = True
                print(f"  ✅ FOUND! Endpoint is registered correctly\n")
    
    if found:
        print("✅ Verification PASSED")
        print("\nEndpoint details:")
        print(f"  Path: {target_path}")
        print(f"  Method: GET")
        print(f"  Query params: lookback_days (default: 30, range: 1-90)")
        print(f"\nResponse structure:")
        print(f"  - meeting: {{title, start_time, attendees, location}}")
        print(f"  - context: {{last_touchpoints, open_loops, shared_files}}")
        print(f"  - suggested_talking_points: [string]")
        print(f"  - why: {{reasons, confidence, sources}}")
        return True
    else:
        print("❌ Verification FAILED")
        print(f"Endpoint {target_path} not found in registered routes")
        return False

if __name__ == "__main__":
    success = verify_endpoint()
    sys.exit(0 if success else 1)
