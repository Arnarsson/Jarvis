"""Heuristic email classifier.

Pure-Python rule-based classifier that assigns one of four categories
to an email message based on sender, subject, and metadata patterns.
No LLM calls, no external dependencies.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis_server.email.models import EmailMessage

# ---------------------------------------------------------------------------
# Pattern lists
# ---------------------------------------------------------------------------

NOTIFICATION_SENDERS = re.compile(
    r"noreply|no-reply|no\.reply|notifications?@|alert@|mailer-daemon|postmaster"
    r"|github\.com|gitlab\.com|jira|circleci|sentry\.io|stripe\.com"
    r"|billing@|support@.*\.noreply|builds@|ci@|deploy@"
    r"|bitbucket\.org|travis-ci|jenkins|datadog|pagerduty|opsgenie"
    r"|vercel\.com|netlify\.com|heroku\.com|aws\.amazon\.com"
    r"|slack\.com|linear\.app|notion\.so|figma\.com|asana\.com"
    r"|feedback@|account@|security@|admin@|system@",
    re.IGNORECASE,
)

NEWSLETTER_SENDERS = re.compile(
    r"substack\.com|mailchimp|campaign-archive|sendinblue|convertkit"
    r"|buttondown\.email|revue\.email|beehiiv\.com|ghost\.io"
    r"|email\.mg\.|mail\.beehiiv|news@|digest@|newsletter@|weekly@|updates@"
    r"|newsletter|noreply@.*\.beehiiv|forwardfuture\.ai",
    re.IGNORECASE,
)

NEWSLETTER_SUBJECT = re.compile(
    r"\bnewsletter\b|\bdigest\b|\bweekly\b|\bmonthly\b|\broundup\b|\bissue\s*#?\d+",
    re.IGNORECASE,
)

UNSUBSCRIBE_PATTERN = re.compile(
    r"unsubscribe|list-unsubscribe|opt.out|email preferences|manage.subscriptions",
    re.IGNORECASE,
)


def classify_email(message: EmailMessage) -> str:
    """Classify an email message into one of four categories.

    Rules are applied in order:
    1. notification - automated system emails
    2. newsletter - subscriptions, digests, marketing
    3. low_priority - CC-only, mass sends
    4. priority - everything else (real person, direct message)

    Args:
        message: An EmailMessage ORM instance.

    Returns:
        One of: 'priority', 'newsletter', 'notification', 'low_priority'
    """
    from_addr = (message.from_address or "").lower()
    subject = message.subject or ""
    snippet = message.snippet or ""
    body = message.body_text or ""
    labels_raw = message.labels_json or ""

    # --- 1. Notification check ---
    if NOTIFICATION_SENDERS.search(from_addr):
        return "notification"

    # --- 2. Newsletter check ---
    if NEWSLETTER_SENDERS.search(from_addr):
        return "newsletter"

    if NEWSLETTER_SUBJECT.search(subject):
        return "newsletter"

    # Check body/snippet for unsubscribe signals
    if UNSUBSCRIBE_PATTERN.search(body[:2000]) or UNSUBSCRIBE_PATTERN.search(snippet):
        return "newsletter"

    # Check labels for list-unsubscribe (Gmail surfaces this as a label/header)
    if "list-unsubscribe" in labels_raw.lower():
        return "newsletter"

    # --- 3. Low priority check ---
    if _is_low_priority(message, from_addr):
        return "low_priority"

    # --- 4. Default: priority ---
    return "priority"


def _is_low_priority(message: EmailMessage, from_addr: str) -> bool:
    """Check if message is low priority based on recipient position and sender."""
    # User only in CC, not in TO
    to_addrs = _parse_address_list(message.to_addresses)
    cc_addrs = _parse_address_list(message.cc_addresses)

    # If there are CC addresses but no TO addresses include the user's address,
    # this might be a CC-only thread. We check if the user appears only in CC.
    # Since we don't know the user's address, we use a heuristic:
    # if cc_addrs exist and to_addrs has many recipients, it's likely a mass send.
    if cc_addrs and len(to_addrs) > 5:
        return True

    # Large number of TO recipients suggests mass-send
    if len(to_addrs) > 10:
        return True

    return False


def _parse_address_list(raw: str | None) -> list[str]:
    """Parse a JSON array of addresses, returning empty list on failure."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return []
