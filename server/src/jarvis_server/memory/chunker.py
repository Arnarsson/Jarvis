"""Conversation chunker - splits conversations into semantic chunks.

Splits conversations into ~500 token chunks (~2000 chars) with overlap,
preserving message boundaries for better context.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Message role prefixes to detect boundaries
MESSAGE_PATTERNS = [
    r"^Human:",
    r"^Assistant:",
    r"^User:",
    r"^ChatGPT:",
    r"^Claude:",
    r"^System:",
    r"^AI:",
]

# Compile patterns for efficiency
MESSAGE_REGEX = re.compile(
    "|".join(f"({p})" for p in MESSAGE_PATTERNS),
    flags=re.MULTILINE | re.IGNORECASE
)


@dataclass
class ConversationChunk:
    """A chunk of conversation text with metadata."""
    conversation_id: str
    source: str  # chatgpt, claude, grok
    title: str
    chunk_text: str
    chunk_index: int
    total_chunks: int
    conversation_date: str | None  # ISO format


def split_into_messages(full_text: str) -> list[str]:
    """Split conversation text into individual messages.
    
    Args:
        full_text: Full conversation text
        
    Returns:
        List of message strings (including role prefix)
    """
    # Find all message boundaries
    matches = list(MESSAGE_REGEX.finditer(full_text))
    
    if not matches:
        # No clear message boundaries - return whole text as one message
        return [full_text]
    
    messages = []
    for i, match in enumerate(matches):
        start = match.start()
        # End is either the next match or end of text
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        message = full_text[start:end].strip()
        if message:
            messages.append(message)
    
    return messages


def chunk_conversation(
    conversation_id: str,
    source: str,
    title: str,
    full_text: str,
    conversation_date: str | None,
    target_chars: int = 2000,
    overlap_chars: int = 200
) -> list[ConversationChunk]:
    """Split conversation into overlapping chunks preserving message boundaries.
    
    Args:
        conversation_id: Unique conversation ID
        source: Source system (chatgpt, claude, grok)
        title: Conversation title
        full_text: Full conversation text
        conversation_date: ISO format date string
        target_chars: Target size for each chunk (~500 tokens)
        overlap_chars: Overlap between chunks for context
        
    Returns:
        List of ConversationChunk objects
    """
    # Split into messages
    messages = split_into_messages(full_text)
    
    if not messages:
        logger.warning(f"No messages found in conversation {conversation_id}")
        return []
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for message in messages:
        message_size = len(message)
        
        # If adding this message would exceed target, finalize current chunk
        if current_chunk and current_size + message_size > target_chars:
            # Create chunk from accumulated messages
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)
            
            # Start new chunk with overlap
            # Keep last few messages for context
            overlap_messages = []
            overlap_size = 0
            for msg in reversed(current_chunk):
                if overlap_size + len(msg) <= overlap_chars:
                    overlap_messages.insert(0, msg)
                    overlap_size += len(msg)
                else:
                    break
            
            current_chunk = overlap_messages
            current_size = overlap_size
        
        # Add message to current chunk
        current_chunk.append(message)
        current_size += message_size
    
    # Don't forget the last chunk
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append(chunk_text)
    
    # If we have no chunks, return the whole conversation as one chunk
    if not chunks:
        chunks = [full_text]
    
    # Create ConversationChunk objects
    total_chunks = len(chunks)
    chunk_objects = [
        ConversationChunk(
            conversation_id=conversation_id,
            source=source,
            title=title,
            chunk_text=text,
            chunk_index=i,
            total_chunks=total_chunks,
            conversation_date=conversation_date
        )
        for i, text in enumerate(chunks)
    ]
    
    logger.debug(
        f"Chunked conversation {conversation_id}: "
        f"{len(full_text)} chars → {total_chunks} chunks"
    )
    
    return chunk_objects


def estimate_token_count(text: str) -> int:
    """Rough token count estimation (1 token ≈ 4 chars)."""
    return len(text) // 4
