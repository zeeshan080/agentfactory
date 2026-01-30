"""FTE (Full-Time Equivalent) Agent System.

This module provides the agent orchestration layer:
- triage.py: Agent selection and creation based on mode
- state.py: Request state and context management
- tools.py: Agent tools for content access
"""

from .state import AgentState, create_state_from_context
from .tools import CONTENT_TOOLS, get_chapter_lessons, load_lesson
from .triage import (
    ASK_PROMPT,
    TEACH_PROMPT,
    create_agent,
    get_agent_for_mode,
)

__all__ = [
    # State management
    "AgentState",
    "create_state_from_context",
    # Triage / agent selection
    "create_agent",
    "get_agent_for_mode",
    "TEACH_PROMPT",
    "ASK_PROMPT",
    # Tools
    "load_lesson",
    "get_chapter_lessons",
    "CONTENT_TOOLS",
]
