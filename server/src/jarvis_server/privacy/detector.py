"""PII detection using Microsoft Presidio.

Provides detection and anonymization of sensitive content including:
- Credit card numbers
- Social Security Numbers (US SSN)
- Phone numbers
- Email addresses
- IP addresses
- Cryptocurrency wallet addresses
- API keys (custom patterns)

The AnalyzerEngine is lazily initialized on first use to avoid startup delay.

Usage:
    from jarvis_server.privacy import PIIDetector

    detector = PIIDetector()
    if detector.has_pii(text):
        summary = detector.get_pii_summary(text)
        anonymized = detector.anonymize(text)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine


@dataclass
class PIIResult:
    """Result of PII detection for a single entity.

    Attributes:
        entity_type: Type of PII detected (e.g., "CREDIT_CARD", "EMAIL_ADDRESS")
        start: Start index in text
        end: End index in text
        score: Confidence score (0.0 to 1.0)
        text_snippet: Masked snippet showing first/last chars only
    """

    entity_type: str
    start: int
    end: int
    score: float
    text_snippet: str


# Common API key patterns for custom recognition
# Patterns are ordered from most specific to least to avoid false positives
API_KEY_PATTERNS = [
    # Stripe keys (most common)
    (r"sk_live_[a-zA-Z0-9]{24,}", "STRIPE_SECRET_KEY"),
    (r"sk_test_[a-zA-Z0-9]{24,}", "STRIPE_TEST_KEY"),
    (r"pk_live_[a-zA-Z0-9]{24,}", "STRIPE_PUBLIC_KEY"),
    (r"pk_test_[a-zA-Z0-9]{24,}", "STRIPE_PUBLIC_KEY"),
    # GitHub tokens (specific prefixes)
    (r"ghp_[a-zA-Z0-9]{36}", "GITHUB_PAT"),
    (r"gho_[a-zA-Z0-9]{36}", "GITHUB_OAUTH"),
    (r"ghs_[a-zA-Z0-9]{36}", "GITHUB_APP_TOKEN"),
    (r"ghu_[a-zA-Z0-9]{36}", "GITHUB_USER_TOKEN"),
    (r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}", "GITHUB_PAT_FINE"),
    # AWS keys (very specific pattern)
    (r"AKIA[0-9A-Z]{16}", "AWS_ACCESS_KEY"),
    (r"ASIA[0-9A-Z]{16}", "AWS_SESSION_KEY"),
    # OpenAI (sk- followed by specific format - proj or just alphanumeric)
    (r"sk-proj-[a-zA-Z0-9_-]{80,}", "OPENAI_PROJECT_KEY"),
    (r"sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}", "OPENAI_API_KEY"),
    # Anthropic
    (r"sk-ant-api[a-zA-Z0-9-]{90,}", "ANTHROPIC_API_KEY"),
    # Google Cloud
    (r"AIza[a-zA-Z0-9_-]{35}", "GOOGLE_API_KEY"),
    # Slack
    (r"xox[baprs]-[a-zA-Z0-9-]{10,}", "SLACK_TOKEN"),
    # Generic patterns (less specific, checked last)
    (r"api[_-]?key[_-]?[=:]\s*['\"]?[a-zA-Z0-9_-]{20,}['\"]?", "GENERIC_API_KEY"),
    (r"bearer\s+[a-zA-Z0-9_.-]{20,}", "BEARER_TOKEN"),
]


class PIIDetector:
    """Detects and anonymizes PII in text using Microsoft Presidio.

    Uses lazy initialization to avoid slow startup (Presidio loads NLP models).
    The analyzer is initialized on first use.

    Attributes:
        score_threshold: Minimum confidence score to consider a detection valid
    """

    def __init__(self, score_threshold: float = 0.5) -> None:
        """Initialize PII detector.

        Args:
            score_threshold: Minimum confidence score (0.0-1.0) for detections.
                            Lower values catch more potential PII but may have
                            more false positives.
        """
        self.score_threshold = score_threshold
        self._analyzer: AnalyzerEngine | None = None
        self._anonymizer: AnonymizerEngine | None = None
        self._api_key_patterns = [
            (re.compile(pattern, re.IGNORECASE), key_type)
            for pattern, key_type in API_KEY_PATTERNS
        ]

        # Entity types to detect (from SEC-01 requirements)
        self._entities = [
            "CREDIT_CARD",
            "US_SSN",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "IP_ADDRESS",
            "CRYPTO",
            "IBAN_CODE",
        ]

    def _ensure_initialized(self) -> None:
        """Lazily initialize Presidio engines on first use.

        This avoids the 5-10 second delay on application startup by
        deferring model loading until actually needed.
        """
        if self._analyzer is None:
            from presidio_analyzer import AnalyzerEngine

            self._analyzer = AnalyzerEngine()

        if self._anonymizer is None:
            from presidio_anonymizer import AnonymizerEngine

            self._anonymizer = AnonymizerEngine()

    def _detect_api_keys(self, text: str) -> list[PIIResult]:
        """Detect API keys using custom regex patterns.

        Args:
            text: Text to analyze

        Returns:
            List of PIIResult for detected API keys
        """
        results = []
        for pattern, key_type in self._api_key_patterns:
            for match in pattern.finditer(text):
                results.append(
                    PIIResult(
                        entity_type=key_type,
                        start=match.start(),
                        end=match.end(),
                        score=0.95,  # High confidence for exact pattern match
                        text_snippet=self._mask_text(match.group()),
                    )
                )
        return results

    def _mask_text(self, text: str) -> str:
        """Create a masked snippet showing only first and last characters.

        Args:
            text: Original text to mask

        Returns:
            Masked text like "4111***1111" or "s***e" for short text
        """
        if len(text) <= 4:
            return text[0] + "***" + text[-1] if len(text) > 1 else "***"
        # Show first 4 and last 4 chars for longer strings
        return text[:4] + "***" + text[-4:]

    def _convert_results(
        self, results: list[RecognizerResult], text: str
    ) -> list[PIIResult]:
        """Convert Presidio results to PIIResult objects.

        Args:
            results: Presidio analyzer results
            text: Original text analyzed

        Returns:
            List of PIIResult objects
        """
        return [
            PIIResult(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=r.score,
                text_snippet=self._mask_text(text[r.start : r.end]),
            )
            for r in results
            if r.score >= self.score_threshold
        ]

    def detect(self, text: str) -> list[PIIResult]:
        """Analyze text for PII.

        Args:
            text: Text to analyze for PII

        Returns:
            List of PIIResult objects with detected PII details
        """
        self._ensure_initialized()

        # Presidio detection
        assert self._analyzer is not None  # For type checker
        presidio_results = self._analyzer.analyze(
            text=text,
            language="en",
            entities=self._entities,
        )

        results = self._convert_results(presidio_results, text)

        # Add API key detections
        api_key_results = self._detect_api_keys(text)
        results.extend(api_key_results)

        # Sort by position in text
        results.sort(key=lambda r: r.start)

        return results

    def has_pii(self, text: str) -> bool:
        """Quick check if any PII is detected.

        Args:
            text: Text to analyze

        Returns:
            True if any PII detected, False otherwise
        """
        # Quick API key check first (cheaper than Presidio)
        for pattern, _ in self._api_key_patterns:
            if pattern.search(text):
                return True

        # Full Presidio analysis
        self._ensure_initialized()
        assert self._analyzer is not None
        results = self._analyzer.analyze(
            text=text,
            language="en",
            entities=self._entities,
            score_threshold=self.score_threshold,
        )
        return len(results) > 0

    def anonymize(self, text: str) -> str:
        """Replace detected PII with placeholders.

        Args:
            text: Text containing PII

        Returns:
            Text with PII replaced by placeholders like <CREDIT_CARD>

        Example:
            >>> detector.anonymize("My card is 4111-1111-1111-1111")
            "My card is <CREDIT_CARD>"
        """
        self._ensure_initialized()
        assert self._analyzer is not None
        assert self._anonymizer is not None

        # Detect PII with Presidio
        results = self._analyzer.analyze(
            text=text,
            language="en",
            entities=self._entities,
            score_threshold=self.score_threshold,
        )

        # Anonymize Presidio detections
        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
        )
        text = anonymized.text

        # Also anonymize API keys (not handled by Presidio)
        for pattern, key_type in self._api_key_patterns:
            text = pattern.sub(f"<{key_type}>", text)

        return text

    def get_pii_summary(self, text: str) -> dict:
        """Get a summary of PII detected in text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with:
                - has_pii: bool indicating if any PII was found
                - types: list of unique PII types found
                - count: total number of PII instances
        """
        results = self.detect(text)
        types = list({r.entity_type for r in results})
        return {
            "has_pii": len(results) > 0,
            "types": types,
            "count": len(results),
        }
