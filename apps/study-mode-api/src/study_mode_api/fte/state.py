"""Agent state management - all context data for FTE agents.

This module centralizes all state/context passed between components:
- User identity and session info
- Lesson content and metadata
- Mode selection (teach/ask)
- Thread context for conversation continuity
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..chatkit_store import RequestContext


@dataclass
class AgentState:
    """
    Centralized state for agent execution.

    All data needed by agents flows through this state object,
    making it easy to extend for multi-agent systems.
    """

    # User identification
    user_id: str
    user_name: str | None = None

    # Session context
    request_id: str | None = None
    organization_id: str | None = None

    # Lesson context
    lesson_path: str = ""
    lesson_title: str = "Unknown"
    lesson_content: str = ""
    content_cached: bool = False

    # Agent mode
    mode: str = "teach"  # "teach" or "ask"

    # Thread context (for conversation continuity)
    thread_id: str | None = None

    # Extensible metadata for future multi-agent needs
    metadata: dict = field(default_factory=dict)

    @property
    def has_content(self) -> bool:
        """Check if lesson content is available."""
        return bool(self.lesson_content)

    @property
    def is_teach_mode(self) -> bool:
        """Check if in Socratic teaching mode."""
        return self.mode == "teach"

    @property
    def is_ask_mode(self) -> bool:
        """Check if in direct answer mode."""
        return self.mode == "ask"


def create_state_from_context(
    context: "RequestContext",
    content_data: dict | None = None,
    thread_id: str | None = None,
) -> AgentState:
    """
    Create AgentState from ChatKit RequestContext.

    Args:
        context: ChatKit request context with user_id and metadata
        content_data: Optional loaded lesson content dict
        thread_id: Optional thread ID for conversation context

    Returns:
        Populated AgentState instance
    """
    metadata = context.metadata or {}
    content = content_data or {}

    return AgentState(
        # User identification
        user_id=context.user_id,
        user_name=metadata.get("user_name"),
        # Session context
        request_id=context.request_id,
        organization_id=context.organization_id,
        # Lesson context
        lesson_path=metadata.get("lesson_path", ""),
        lesson_title=content.get("title", "Unknown"),
        lesson_content=content.get("content", ""),
        content_cached=content.get("cached", False),
        # Agent mode
        mode=metadata.get("mode", "teach"),
        # Thread context
        thread_id=thread_id,
        # Pass through any extra metadata
        metadata={k: v for k, v in metadata.items()
                  if k not in ("user_name", "lesson_path", "mode")},
    )
