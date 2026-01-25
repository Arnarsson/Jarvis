#!/usr/bin/env python3
"""Local OAuth helper for Google Calendar.

Run this script outside Docker to complete OAuth flow.
It generates token.json that Docker can use.

Usage:
    python scripts/oauth_helper.py
"""

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.parent
CREDS_PATH = SCRIPT_DIR / "data" / "calendar" / "credentials.json"
TOKEN_PATH = SCRIPT_DIR / "data" / "calendar" / "token.json"


def main():
    if not CREDS_PATH.exists():
        print(f"ERROR: credentials.json not found at {CREDS_PATH}")
        print("Download it from Google Cloud Console and place it there.")
        return 1

    print(f"Using credentials from: {CREDS_PATH}")
    print(f"Token will be saved to: {TOKEN_PATH}")
    print()
    print("Opening browser for Google sign-in...")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
    creds = flow.run_local_server(port=8090)

    # Save token
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())

    print()
    print(f"SUCCESS! Token saved to {TOKEN_PATH}")
    print("The Docker container can now access Google Calendar.")
    print()
    print("Test it with:")
    print("  curl http://localhost:8000/api/calendar/auth/status")

    return 0


if __name__ == "__main__":
    exit(main())
