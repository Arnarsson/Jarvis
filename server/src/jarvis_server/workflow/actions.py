"""Action handlers for workflow execution.

Each handler implements validate/execute/undo for a specific action type.
"""

import logging
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of executing a single action."""
    success: bool
    action_type: str
    message: str
    undo_state: Optional[dict] = None


class ActionHandler(ABC):
    """Base class for action handlers."""

    action_type: str = ""

    @abstractmethod
    def validate(self, params: dict) -> bool:
        """Validate action parameters before execution."""
        ...

    @abstractmethod
    async def execute(self, params: dict) -> ActionResult:
        """Execute the action."""
        ...

    async def undo(self, undo_state: dict) -> bool:
        """Undo the action. Returns True if undo succeeded."""
        logger.info(f"[UNDO] {self.action_type}: no undo implemented, state={undo_state}")
        return False


class NotifyAction(ActionHandler):
    """Send a notification (always safe)."""

    action_type = "notify"

    def validate(self, params: dict) -> bool:
        return bool(params.get("message"))

    async def execute(self, params: dict) -> ActionResult:
        message = params.get("message", "Jarvis automation triggered")
        logger.info(f"[JARVIS NOTIFY] {message}")
        return ActionResult(
            success=True,
            action_type=self.action_type,
            message=f"Notification: {message}",
        )


class OpenAppAction(ActionHandler):
    """Open an application."""

    action_type = "open_app"

    def validate(self, params: dict) -> bool:
        return bool(params.get("app"))

    async def execute(self, params: dict) -> ActionResult:
        app_name = params.get("app", "")
        if not app_name:
            return ActionResult(False, self.action_type, "No application specified")
        # TODO: integrate with desktop agent via D-Bus or HTTP
        logger.info(f"[JARVIS OPEN_APP] {app_name}")
        return ActionResult(
            success=True,
            action_type=self.action_type,
            message=f"Would open app: {app_name}",
            undo_state={"action": "close_app", "app": app_name},
        )

    async def undo(self, undo_state: dict) -> bool:
        app = undo_state.get("app", "")
        logger.info(f"[JARVIS UNDO] close app: {app}")
        return True


class OpenUrlAction(ActionHandler):
    """Open a URL in the browser."""

    action_type = "open_url"

    def validate(self, params: dict) -> bool:
        url = params.get("url", "")
        return url.startswith("http://") or url.startswith("https://")

    async def execute(self, params: dict) -> ActionResult:
        url = params.get("url", "")
        if not url:
            return ActionResult(False, self.action_type, "No URL provided")
        logger.info(f"[JARVIS OPEN_URL] {url}")
        return ActionResult(
            success=True,
            action_type=self.action_type,
            message=f"Would open URL: {url}",
            undo_state={"action": "close_tab", "url": url},
        )

    async def undo(self, undo_state: dict) -> bool:
        url = undo_state.get("url", "")
        logger.info(f"[JARVIS UNDO] close tab: {url}")
        return True


class TypeTextAction(ActionHandler):
    """Type predefined text (simulated keyboard input)."""

    action_type = "type_text"

    def validate(self, params: dict) -> bool:
        return bool(params.get("text"))

    async def execute(self, params: dict) -> ActionResult:
        text = params.get("text", "")
        if not text:
            return ActionResult(False, self.action_type, "No text provided")
        # TODO: integrate with desktop agent for keyboard simulation
        preview = text[:50] + ("..." if len(text) > 50 else "")
        logger.info(f"[JARVIS TYPE_TEXT] {preview}")
        return ActionResult(
            success=True,
            action_type=self.action_type,
            message=f"Would type: {preview}",
            undo_state={"action": "undo_type", "length": len(text)},
        )

    async def undo(self, undo_state: dict) -> bool:
        length = undo_state.get("length", 0)
        logger.info(f"[JARVIS UNDO] undo {length} chars of typed text")
        return True


class ScriptAction(ActionHandler):
    """Execute an approved shell script (sandboxed)."""

    action_type = "run_script"

    BLOCKED_COMMANDS = {"rm -rf", "dd if=", "mkfs", "> /dev/", ":(){ :|:& };:"}

    def validate(self, params: dict) -> bool:
        script = params.get("script", "")
        if not script:
            return False
        lowered = script.lower()
        return not any(blocked in lowered for blocked in self.BLOCKED_COMMANDS)

    async def execute(self, params: dict) -> ActionResult:
        script = params.get("script", "")
        if not script:
            return ActionResult(False, self.action_type, "No script provided")
        if not self.validate(params):
            return ActionResult(False, self.action_type, "Script blocked by safety filter")
        # TODO: execute in sandbox (firejail, bubblewrap, or container)
        preview = script[:80] + ("..." if len(script) > 80 else "")
        logger.info(f"[JARVIS RUN_SCRIPT] {preview}")
        return ActionResult(
            success=True,
            action_type=self.action_type,
            message=f"Would run script: {preview}",
            undo_state={"action": "script_ran", "script": script},
        )


class SendMessageAction(ActionHandler):
    """Send a message via a configured channel."""

    action_type = "send_message"

    def validate(self, params: dict) -> bool:
        return bool(params.get("channel")) and bool(params.get("message"))

    async def execute(self, params: dict) -> ActionResult:
        channel = params.get("channel", "")
        message = params.get("message", "")
        if not channel or not message:
            return ActionResult(False, self.action_type, "Channel and message required")
        # TODO: integrate with messaging APIs
        preview = message[:50] + ("..." if len(message) > 50 else "")
        logger.info(f"[JARVIS SEND_MESSAGE] to {channel}: {preview}")
        return ActionResult(
            success=True,
            action_type=self.action_type,
            message=f"Would send to {channel}: {preview}",
            undo_state={"action": "message_sent", "channel": channel},
        )


# Registry of all action handlers
ACTION_HANDLERS: dict[str, ActionHandler] = {
    "notify": NotifyAction(),
    "open_app": OpenAppAction(),
    "open_url": OpenUrlAction(),
    "type_text": TypeTextAction(),
    "run_script": ScriptAction(),
    "send_message": SendMessageAction(),
}


def get_handler(action_type: str) -> Optional[ActionHandler]:
    """Get the handler for an action type."""
    return ACTION_HANDLERS.get(action_type.lower())
