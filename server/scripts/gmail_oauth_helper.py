#!/usr/bin/env python3
"""Local OAuth helper for Gmail.

Run this script outside Docker to complete Gmail OAuth flow.
It generates token.json that Docker can use.

Usage:
    python scripts/gmail_oauth_helper.py

Prerequisites:
    1. Enable Gmail API in Google Cloud Console
    2. Copy credentials.json to server/data/email/
"""

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.parent
CREDS_PATH = SCRIPT_DIR / "data" / "email" / "credentials.json"
TOKEN_PATH = SCRIPT_DIR / "data" / "email" / "token.json"


def main():
    if not CREDS_PATH.exists():
        # Try to copy from calendar
        calendar_creds = SCRIPT_DIR / "data" / "calendar" / "credentials.json"
        if calendar_creds.exists():
            print(f"Copying credentials from calendar setup...")
            CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
            CREDS_PATH.write_text(calendar_creds.read_text())
        else:
            print(f"ERROR: credentials.json not found at {CREDS_PATH}")
            print("Download it from Google Cloud Console and place it there.")
            print("Or copy from server/data/calendar/credentials.json")
            return 1

    print(f"Using credentials from: {CREDS_PATH}")
    print(f"Token will be saved to: {TOKEN_PATH}")
    print()
    print("Opening browser for Google sign-in (Gmail read-only access)...")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
    creds = flow.run_local_server(port=8091)  # Different port than calendar

    # Save token
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())

    print()
    print(f"SUCCESS! Token saved to {TOKEN_PATH}")
    print("Now copy the token to Docker:")
    print()
    print("  docker cp server/data/email/token.json jarvis-server:/data/email/token.json")
    print()
    print("Then test with:")
    print("  curl http://localhost:8000/api/email/auth/status")

    return 0


if __name__ == "__main__":
    exit(main())
