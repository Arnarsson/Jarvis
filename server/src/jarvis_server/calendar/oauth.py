"""Google Calendar OAuth2 authentication module.

Handles OAuth2 flow for Google Calendar API access with token persistence.
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

# Read-only calendar access for v1
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Default data directory paths
_data_dir = Path(os.getenv("JARVIS_DATA_DIR", "/data"))
TOKEN_PATH = _data_dir / "calendar" / "token.json"
CREDS_PATH = _data_dir / "calendar" / "credentials.json"


class CalendarAuthRequired(Exception):
    """Raised when calendar OAuth authentication is needed.

    This exception indicates that the user needs to complete the OAuth flow
    before calendar features can be used.
    """

    pass


class CredentialsNotFound(Exception):
    """Raised when OAuth credentials file is missing.

    The user must download credentials.json from Google Cloud Console
    and place it in the expected location.
    """

    pass


def _ensure_token_dir() -> None:
    """Ensure the token directory exists."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)


def is_authenticated() -> bool:
    """Check if valid OAuth credentials exist.

    Returns:
        True if a valid (or refreshable) token exists, False otherwise.
    """
    if not TOKEN_PATH.exists():
        return False

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        # Check if credentials are valid or can be refreshed
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            return True
        return False
    except Exception:
        return False


def credentials_exist() -> bool:
    """Check if OAuth credentials file (credentials.json) exists.

    Returns:
        True if credentials.json exists, False otherwise.
    """
    return CREDS_PATH.exists()


def get_calendar_service() -> Resource:
    """Get authenticated Google Calendar API service.

    Returns:
        Google Calendar API service resource.

    Raises:
        CalendarAuthRequired: If no valid credentials exist.
    """
    creds = None

    # Load existing token if available
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # If no valid credentials, need auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh the token
            creds.refresh(Request())
            # Save refreshed token
            _ensure_token_dir()
            TOKEN_PATH.write_text(creds.to_json())
        else:
            raise CalendarAuthRequired(
                "Calendar authentication required. "
                "Please complete OAuth flow via /api/calendar/auth/start"
            )

    return build("calendar", "v3", credentials=creds)


def start_oauth_flow(port: int = 8090) -> str:
    """Start the OAuth2 flow for Google Calendar authentication.

    This runs a local server to handle the OAuth callback.
    The user must have access to a browser on the same machine.

    Args:
        port: Local port for OAuth callback server (default 8090).

    Returns:
        Success message after authentication completes.

    Raises:
        CredentialsNotFound: If credentials.json is missing.
    """
    if not CREDS_PATH.exists():
        raise CredentialsNotFound(
            f"OAuth credentials not found at {CREDS_PATH}. "
            "Download credentials.json from Google Cloud Console and place it there."
        )

    # Create the flow using the client secrets file
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)

    # Run the local server OAuth flow
    creds = flow.run_local_server(port=port)

    # Save the credentials for future use
    _ensure_token_dir()
    TOKEN_PATH.write_text(creds.to_json())

    return "Authentication successful"
