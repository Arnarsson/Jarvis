"""Safety classification for workflow actions.

Classifies actions by risk level to prevent destructive automations
from executing without explicit user approval.
"""

import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyLevel(str, Enum):
    """Safety classification for actions."""
    SAFE = "safe"              # Can auto-execute
    CAUTION = "caution"        # Requires confirmation on first use
    DESTRUCTIVE = "destructive"  # Always requires approval


class SafetyClassifier:
    """Classifies action safety levels based on keywords and action type."""

    DESTRUCTIVE_KEYWORDS = [
        "delete", "remove", "drop", "destroy", "wipe", "purge",
        "send_email", "send_message", "post", "publish",
        "payment", "transfer", "purchase", "buy",
        "shutdown", "reboot", "restart_system",
        "format", "truncate", "overwrite",
    ]

    CAUTION_KEYWORDS = [
        "modify", "update", "change", "edit",
        "create", "new", "add",
        "api_call", "webhook", "http_request",
        "move", "rename", "copy",
    ]

    # Action types that are always safe regardless of params
    SAFE_ACTION_TYPES = {"notify"}

    # Action types that are always at least caution level
    CAUTION_ACTION_TYPES = {"run_script", "send_message"}

    @classmethod
    def classify(cls, action: dict) -> SafetyLevel:
        """Classify an action's safety level."""
        action_type = action.get("type", "").lower()

        if action_type in cls.SAFE_ACTION_TYPES:
            return SafetyLevel.SAFE

        if action_type in cls.CAUTION_ACTION_TYPES:
            # Still check for destructive keywords
            action_str = json.dumps(action).lower()
            for keyword in cls.DESTRUCTIVE_KEYWORDS:
                if keyword in action_str:
                    return SafetyLevel.DESTRUCTIVE
            return SafetyLevel.CAUTION

        # General keyword scan
        action_str = json.dumps(action).lower()
        for keyword in cls.DESTRUCTIVE_KEYWORDS:
            if keyword in action_str:
                return SafetyLevel.DESTRUCTIVE

        for keyword in cls.CAUTION_KEYWORDS:
            if keyword in action_str:
                return SafetyLevel.CAUTION

        return SafetyLevel.SAFE

    @classmethod
    def is_destructive(cls, action: dict) -> bool:
        """Check if an action is destructive."""
        return cls.classify(action) == SafetyLevel.DESTRUCTIVE

    @classmethod
    def classify_all(cls, actions: list[dict]) -> SafetyLevel:
        """Return the highest safety level across all actions."""
        highest = SafetyLevel.SAFE
        for action in actions:
            level = cls.classify(action)
            if level == SafetyLevel.DESTRUCTIVE:
                return SafetyLevel.DESTRUCTIVE
            if level == SafetyLevel.CAUTION:
                highest = SafetyLevel.CAUTION
        return highest

    @classmethod
    def get_report(cls, actions: list[dict]) -> list[dict]:
        """Return a per-action safety report."""
        return [
            {
                "action_type": a.get("type", "unknown"),
                "safety_level": cls.classify(a).value,
                "is_destructive": cls.is_destructive(a),
            }
            for a in actions
        ]
