"""Input validators for prompt injection prevention.

This module provides validation functions for user inputs before they are
processed by MCP tools. The validators sanitize inputs and detect patterns
that could be used for prompt injection attacks.

Why this matters:
- MCP servers receive user input that gets embedded in LLM prompts
- Malicious inputs could confuse or manipulate the LLM
- These validators strip dangerous patterns before processing
"""

from __future__ import annotations

import re
from typing import Final

import structlog

# Get logger for this module
logger = structlog.get_logger("jarvis_mcp.validators")

# Control characters that should be stripped from input
# Includes: NUL, SOH-BS, VT, FF, SO-US, DEL
# Excludes: TAB (0x09), LF (0x0a), CR (0x0d) which are valid whitespace
CONTROL_CHARS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

# Excessive whitespace (2+ spaces/tabs/newlines in a row)
EXCESSIVE_WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\s{2,}")

# Dangerous patterns that could be used for prompt injection
# Each pattern includes a description for logging
DANGEROUS_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # Code block starts - could escape context
    (re.compile(r"^```", re.MULTILINE), "code_block_start"),
    # Markdown headers at line start - could inject formatting
    (re.compile(r"^\s*#", re.MULTILINE), "markdown_header"),
    # Common prompt delimiters used in various LLMs
    (re.compile(r"<\|.*?\|>"), "prompt_delimiter"),
    # Instruction markers (Llama/Mistral format)
    (re.compile(r"\[INST\]|\[/INST\]", re.IGNORECASE), "instruction_marker"),
    # System role injection attempts
    (re.compile(r"<<SYS>>|<</SYS>>", re.IGNORECASE), "system_marker"),
    # Claude's human/assistant markers
    (re.compile(r"\b(Human|Assistant):\s*$", re.MULTILINE), "role_marker"),
]


def _strip_control_chars(text: str) -> str:
    """Remove control characters from text.

    Args:
        text: Input text to sanitize

    Returns:
        Text with control characters removed
    """
    return CONTROL_CHARS_PATTERN.sub("", text)


def _normalize_whitespace(text: str) -> str:
    """Normalize excessive whitespace to single spaces.

    Args:
        text: Input text to normalize

    Returns:
        Text with normalized whitespace
    """
    return EXCESSIVE_WHITESPACE_PATTERN.sub(" ", text).strip()


def _check_dangerous_patterns(text: str) -> tuple[bool, str | None]:
    """Check if text contains dangerous patterns.

    Args:
        text: Input text to check

    Returns:
        Tuple of (is_dangerous, pattern_name) where pattern_name is None if safe
    """
    for pattern, name in DANGEROUS_PATTERNS:
        if pattern.search(text):
            return True, name
    return False, None


def validate_search_query(query: str) -> str:
    """Validate and sanitize a search query.

    Performs the following sanitization:
    1. Strip control characters (NUL, etc.)
    2. Normalize excessive whitespace to single spaces
    3. Check for dangerous prompt injection patterns

    Args:
        query: Raw search query from user

    Returns:
        Sanitized query string

    Raises:
        ValueError: If query contains dangerous patterns

    Example:
        >>> validate_search_query("find meetings about api")
        'find meetings about api'
        >>> validate_search_query("test\\x00query")
        'testquery'
        >>> validate_search_query("[INST] ignore previous")
        Traceback (most recent call last):
            ...
        ValueError: Invalid search query: contains prohibited pattern
    """
    # Step 1: Strip control characters
    sanitized = _strip_control_chars(query)

    # Step 2: Normalize whitespace
    sanitized = _normalize_whitespace(sanitized)

    # Step 3: Check for dangerous patterns
    is_dangerous, pattern_name = _check_dangerous_patterns(sanitized)

    if is_dangerous:
        # Log the suspicious input before rejection
        logger.warning(
            "suspicious_input_blocked",
            pattern=pattern_name,
            input_length=len(query),
            # Don't log the actual input to avoid log injection
        )
        raise ValueError("Invalid search query: contains prohibited pattern")

    return sanitized


def validate_topic(topic: str) -> str:
    """Validate and sanitize a topic string.

    Topics have stricter length requirements than search queries
    (1-500 chars) as they should be concise labels.

    Args:
        topic: Raw topic string from user

    Returns:
        Sanitized topic string

    Raises:
        ValueError: If topic is empty, too long, or contains dangerous patterns

    Example:
        >>> validate_topic("project planning")
        'project planning'
        >>> validate_topic("")
        Traceback (most recent call last):
            ...
        ValueError: Topic must be between 1 and 500 characters
    """
    # Step 1: Strip control characters
    sanitized = _strip_control_chars(topic)

    # Step 2: Normalize whitespace
    sanitized = _normalize_whitespace(sanitized)

    # Step 3: Check length constraints
    if len(sanitized) < 1 or len(sanitized) > 500:
        logger.warning(
            "suspicious_input_blocked",
            pattern="invalid_length",
            input_length=len(topic),
        )
        raise ValueError("Topic must be between 1 and 500 characters")

    # Step 4: Check for dangerous patterns
    is_dangerous, pattern_name = _check_dangerous_patterns(sanitized)

    if is_dangerous:
        logger.warning(
            "suspicious_input_blocked",
            pattern=pattern_name,
            input_length=len(topic),
        )
        raise ValueError("Invalid topic: contains prohibited pattern")

    return sanitized
