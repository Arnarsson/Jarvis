"""Privacy module for Jarvis server.

Provides PII detection and anonymization capabilities using Microsoft Presidio.

Usage:
    from jarvis_server.privacy import PIIDetector, PIIResult

    detector = PIIDetector(score_threshold=0.5)

    # Quick check
    if detector.has_pii(text):
        print("Contains sensitive data!")

    # Get details
    results = detector.detect(text)
    for result in results:
        print(f"Found {result.entity_type} at position {result.start}-{result.end}")

    # Anonymize
    safe_text = detector.anonymize(text)

    # Summary for logging
    summary = detector.get_pii_summary(text)
    # {"has_pii": True, "types": ["CREDIT_CARD", "EMAIL_ADDRESS"], "count": 2}
"""

from jarvis_server.privacy.detector import PIIDetector, PIIResult

__all__ = ["PIIDetector", "PIIResult"]
