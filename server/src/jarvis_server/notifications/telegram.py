"""Telegram notification sender via Clawdbot."""

import asyncio
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)


async def send_telegram_notification(
    message: str,
    target: Optional[str] = None,
    silent: bool = False,
) -> bool:
    """Send a notification via Telegram using Clawdbot.
    
    Args:
        message: The message text to send
        target: Optional target chat/user (defaults to your primary chat)
        silent: If True, send silently without notification sound
        
    Returns:
        True if message was sent successfully, False otherwise
    """
    try:
        cmd = ["clawdbot", "message", "send", "--channel", "telegram", "--message", message]
        
        if target:
            cmd.extend(["--target", target])
        
        if silent:
            cmd.append("--silent")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(
                "telegram_notification_sent",
                message_preview=message[:50],
                target=target,
            )
            return True
        else:
            logger.error(
                "telegram_notification_failed",
                returncode=process.returncode,
                stderr=stderr.decode() if stderr else None,
            )
            return False
            
    except Exception as e:
        logger.error(
            "telegram_notification_error",
            error=str(e),
            exc_info=True,
        )
        return False
