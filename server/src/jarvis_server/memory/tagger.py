"""Tag extractor - extracts metadata from conversation chunks using heuristics.

Extracts people, projects, decisions, action items, topics, dates, and sentiment
without using LLMs (too expensive for 50k+ chunks).
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Stopwords to exclude from topic extraction
STOPWORDS = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for',
    'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but', 'his',
    'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an', 'will', 'my',
    'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out', 'if',
    'about', 'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can', 'like',
    'time', 'no', 'just', 'him', 'know', 'take', 'people', 'into', 'year',
    'your', 'good', 'some', 'could', 'them', 'see', 'other', 'than', 'then',
    'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also', 'back',
    'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way', 'even',
    'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us', 'is',
    'was', 'are', 'been', 'has', 'had', 'were', 'said', 'did', 'having', 'may',
}

# Positive sentiment keywords
POSITIVE_WORDS = {
    'great', 'good', 'excellent', 'awesome', 'perfect', 'love', 'amazing',
    'wonderful', 'fantastic', 'brilliant', 'success', 'agree', 'yes', 'correct',
    'right', 'exactly', 'definitely', 'absolutely', 'thanks', 'thank',
}

# Negative sentiment keywords  
NEGATIVE_WORDS = {
    'bad', 'terrible', 'awful', 'horrible', 'wrong', 'error', 'problem', 'issue',
    'fail', 'failed', 'broken', 'bug', 'no', 'not', 'never', 'cant', 'cannot',
    'dont', 'wont', 'shouldnt', 'wouldnt', 'mistake', 'sorry',
}


@dataclass
class ChunkTags:
    """Extracted tags from a conversation chunk."""
    people: list[str]  # Names mentioned
    projects: list[str]  # Project names
    decisions: list[str]  # Decision sentences
    action_items: list[str]  # Action item sentences
    topics: list[str]  # Top keywords
    dates_mentioned: list[str]  # Dates found in text
    sentiment: str  # positive, negative, neutral


def extract_people(text: str) -> list[str]:
    """Extract person names from text.
    
    Looks for:
    - Capitalized words near 'with', 'from', '@'
    - Multiple consecutive capitalized words (likely names)
    """
    people = set()
    
    # Pattern 1: "with/from NAME"
    pattern1 = r"(?:with|from|to|cc:|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
    matches = re.findall(pattern1, text)
    people.update(matches)
    
    # Pattern 2: "@NAME" or "@ NAME"
    pattern2 = r"@\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
    matches = re.findall(pattern2, text)
    people.update(matches)
    
    # Pattern 3: Multiple consecutive capitalized words (likely full names)
    pattern3 = r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b"
    matches = re.findall(pattern3, text)
    people.update(matches)
    
    # Filter out common false positives
    filtered = []
    for name in people:
        # Skip single common words, months, days
        if name in {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                    'Saturday', 'Sunday', 'January', 'February', 'March',
                    'April', 'May', 'June', 'July', 'August', 'September',
                    'October', 'November', 'December', 'Human', 'Assistant',
                    'User', 'ChatGPT', 'Claude', 'System'}:
            continue
        # Must be at least 2 chars
        if len(name) >= 2:
            filtered.append(name)
    
    return list(set(filtered))[:5]  # Top 5


def extract_projects(text: str) -> list[str]:
    """Extract project names from text.
    
    Looks for:
    - Words after 'project', 'repo', 'repository'
    - GitHub URLs
    - Repeated proper nouns
    """
    projects = []
    
    # Pattern 1: "project NAME" or "repo NAME"
    pattern1 = r"(?:project|repo|repository)\s+([A-Z][a-zA-Z0-9_-]+)"
    matches = re.findall(pattern1, text, re.IGNORECASE)
    projects.extend(matches)
    
    # Pattern 2: GitHub URLs
    pattern2 = r"github\.com/[\w-]+/([\w-]+)"
    matches = re.findall(pattern2, text)
    projects.extend(matches)
    
    # Pattern 3: Repeated capitalized words (likely project names)
    words = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', text)
    word_counts = Counter(words)
    # Add words mentioned 2+ times
    for word, count in word_counts.most_common(10):
        if count >= 2 and word not in {'Human', 'Assistant', 'User', 'ChatGPT', 'Claude'}:
            projects.append(word)
    
    return list(set(projects))[:5]  # Top 5


def extract_decisions(text: str) -> list[str]:
    """Extract decision sentences from text."""
    decision_keywords = [
        'decided', 'agreed', 'will do', 'going with', 'chose', 'selected',
        'picked', 'settled on', 'concluded', 'determined', 'resolved',
    ]
    
    sentences = re.split(r'[.!?]\s+', text)
    decisions = []
    
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in decision_keywords):
            # Clean and truncate
            clean = sentence.strip()
            if len(clean) > 150:
                clean = clean[:147] + "..."
            if clean:
                decisions.append(clean)
    
    return decisions[:3]  # Top 3


def extract_action_items(text: str) -> list[str]:
    """Extract action item sentences from text."""
    action_keywords = [
        'need to', 'should', 'must', 'have to', 'got to', 'ought to',
        'todo', 'to-do', 'action item', 'task:', 'next step',
    ]
    
    sentences = re.split(r'[.!?]\s+', text)
    actions = []
    
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in action_keywords):
            # Clean and truncate
            clean = sentence.strip()
            if len(clean) > 150:
                clean = clean[:147] + "..."
            if clean:
                actions.append(clean)
    
    return actions[:3]  # Top 3


def extract_topics(text: str, top_n: int = 5) -> list[str]:
    """Extract top keywords using simple TF approach.
    
    Args:
        text: Text to extract topics from
        top_n: Number of top keywords to return
        
    Returns:
        List of top keywords
    """
    # Convert to lowercase and extract words
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    
    # Filter stopwords
    filtered = [w for w in words if w not in STOPWORDS]
    
    # Count frequencies
    counts = Counter(filtered)
    
    # Return top N
    return [word for word, _ in counts.most_common(top_n)]


def extract_dates(text: str) -> list[str]:
    """Extract date mentions from text."""
    dates = []
    
    # Pattern 1: YYYY-MM-DD
    pattern1 = r'\b(\d{4}-\d{2}-\d{2})\b'
    dates.extend(re.findall(pattern1, text))
    
    # Pattern 2: Month Day, Year (e.g., "January 26, 2026")
    pattern2 = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
    dates.extend(re.findall(pattern2, text))
    
    # Pattern 3: MM/DD/YYYY or DD/MM/YYYY
    pattern3 = r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b'
    dates.extend(re.findall(pattern3, text))
    
    return list(set(dates))[:5]  # Top 5 unique


def analyze_sentiment(text: str) -> str:
    """Determine sentiment using keyword matching.
    
    Returns:
        'positive', 'negative', or 'neutral'
    """
    text_lower = text.lower()
    
    # Count positive and negative words
    positive_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    negative_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)
    
    # Determine sentiment
    if positive_count > negative_count + 1:
        return 'positive'
    elif negative_count > positive_count + 1:
        return 'negative'
    else:
        return 'neutral'


def extract_tags(chunk_text: str) -> ChunkTags:
    """Extract all tags from a conversation chunk.
    
    Args:
        chunk_text: Text of the conversation chunk
        
    Returns:
        ChunkTags object with all extracted metadata
    """
    return ChunkTags(
        people=extract_people(chunk_text),
        projects=extract_projects(chunk_text),
        decisions=extract_decisions(chunk_text),
        action_items=extract_action_items(chunk_text),
        topics=extract_topics(chunk_text),
        dates_mentioned=extract_dates(chunk_text),
        sentiment=analyze_sentiment(chunk_text),
    )
