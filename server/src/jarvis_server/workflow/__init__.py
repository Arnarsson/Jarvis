"""Workflow automation module for Jarvis.

This module provides pattern detection, automation suggestions,
workflow execution, safety classification, and undo capabilities.
"""

from jarvis_server.workflow.repository import PatternRepository
from jarvis_server.workflow.detector import PatternDetector, DetectedPattern
from jarvis_server.workflow.executor import WorkflowExecutor
from jarvis_server.workflow.safety import SafetyClassifier, SafetyLevel
from jarvis_server.workflow.false_positive import FalsePositiveTracker
from jarvis_server.workflow.undo import UndoManager
from jarvis_server.workflow.actions import ACTION_HANDLERS, get_handler

__all__ = [
    "PatternRepository",
    "PatternDetector",
    "DetectedPattern",
    "WorkflowExecutor",
    "SafetyClassifier",
    "SafetyLevel",
    "FalsePositiveTracker",
    "UndoManager",
    "ACTION_HANDLERS",
    "get_handler",
]
