"""Agent triage - select and create appropriate agent for request.

This module handles agent selection based on mode and context.
Designed to support multi-agent systems in the future.

Current agents:
- teach: Socratic tutor using lesson content
- ask: Direct answer search engine

Future agents could include:
- quiz: Assessment and testing
- review: Spaced repetition
- practice: Hands-on exercises
"""

import os
from typing import TYPE_CHECKING

from agents import Agent, ModelSettings
from openai.types.shared import Reasoning

from .state import AgentState

if TYPE_CHECKING:
    pass

# Model configuration
MODEL = os.getenv("STUDY_MODE_MODEL", "gpt-5-nano-2025-08-07")

# Context limits for content truncation
TEACH_CONTENT_LIMIT = 8000
ASK_CONTENT_LIMIT = 6000

# =============================================================================
# Agent Prompts
# =============================================================================

TEACH_PROMPT = """You are a Socratic tutor for the AgentFactory book.
{user_greeting}

LESSON CONTEXT:
{title}
---
{content}
---

SOCRATIC METHOD RULES:
1. NEVER explain directly - guide through questions instead
2. Start from what the student already knows or thinks
3. Ask ONE question at a time, then wait for their response
4. If student is stuck, give a small hint - never the answer
5. Let them struggle productively (2 attempts) before more help
6. When they discover an insight, reinforce it briefly
7. Connect new ideas to what they already understand
8. Use **bold** for key terms when the student discovers them
9. Be warm and patient, but keep momentum

WHAT TO DO:
- Begin by asking what they already know about the topic
- Use their response to craft the next question
- Lead them to discover concepts through questioning
- Celebrate when they figure things out

WHAT NOT TO DO:
- Don't lecture or explain concepts directly
- Don't answer their questions with answers - respond with guiding questions
- Don't ask more than one question per message
- Don't give up and tell them - keep guiding"""

ASK_PROMPT = """You are a helpful explainer for the AgentFactory book.
{user_greeting}

CONTEXT (the page they're reading):
{content}

WHAT'S HAPPENING:
The student highlighted something or has a specific question about the lesson.
They want a clear explanation, not a Socratic dialogue.

HOW TO RESPOND:
1. Acknowledge what they're asking about
2. Explain it clearly at their level (assume motivated beginner)
3. Connect it to the surrounding context when helpful
4. Use an example or analogy if it aids understanding
5. Keep it focused - answer what they asked

TONE:
- Direct and clear (not robotic)
- Helpful and warm (not dismissive)
- Concise but complete (not artificially brief)

AVOID:
- "Great question!" or similar filler
- Asking follow-up questions (this isn't Socratic mode)
- Over-explaining or going off-topic
- Being so brief that you don't actually help"""

# =============================================================================
# Agent Registry (for future multi-agent support)
# =============================================================================

AGENT_REGISTRY = {
    "teach": {
        "prompt": TEACH_PROMPT,
        "content_limit": TEACH_CONTENT_LIMIT,
        "description": "Socratic tutor - guides through questions, never lectures",
    },
    "ask": {
        "prompt": ASK_PROMPT,
        "content_limit": ASK_CONTENT_LIMIT,
        "description": "Direct explainer for highlighted text and specific questions",
    },
}


def get_available_modes() -> list[str]:
    """Get list of available agent modes."""
    return list(AGENT_REGISTRY.keys())


def get_agent_for_mode(mode: str) -> dict:
    """
    Get agent configuration for a given mode.

    Args:
        mode: Agent mode (teach, ask, etc.)

    Returns:
        Agent configuration dict

    Raises:
        ValueError: If mode is not registered
    """
    if mode not in AGENT_REGISTRY:
        raise ValueError(f"Unknown mode: {mode}. Available: {get_available_modes()}")
    return AGENT_REGISTRY[mode]


def create_agent(
    title: str,
    content: str,
    mode: str = "teach",
    user_name: str | None = None,
) -> Agent:
    """
    Create book-grounded study agent with optional user personalization.

    Args:
        title: Lesson title
        content: Lesson markdown content
        mode: "teach" for Socratic tutoring, "ask" for direct answers
        user_name: Optional student name for personalization

    Returns:
        Configured Agent instance
    """
    agent_config = get_agent_for_mode(mode)
    user_greeting = f"STUDENT: {user_name}" if user_name else ""

    if mode == "teach":
        instructions = agent_config["prompt"].format(
            title=title,
            content=content[:agent_config["content_limit"]],
            user_greeting=user_greeting,
        )
    else:
        instructions = agent_config["prompt"].format(
            content=f"CURRENT: {title}\n{content[:agent_config['content_limit']]}",
            user_greeting=user_greeting,
        )

    return Agent(
        name=f"study_tutor_{mode}",
        instructions=instructions,
        model=MODEL,
        model_settings=ModelSettings(reasoning=Reasoning(effort="minimal")),
    )


def create_agent_from_state(state: AgentState) -> Agent:
    """
    Create agent from AgentState object.

    This is the preferred method for multi-agent systems as it uses
    the centralized state object.

    Args:
        state: AgentState with all necessary context

    Returns:
        Configured Agent instance
    """
    return create_agent(
        title=state.lesson_title,
        content=state.lesson_content,
        mode=state.mode,
        user_name=state.user_name,
    )
