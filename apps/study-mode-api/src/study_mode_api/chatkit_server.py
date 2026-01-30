"""ChatKit server for Study Mode - simple pattern from carfixer reference."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime

from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
    UserMessageTextContent,
)

from .chatkit_store import CachedPostgresStore, PostgresStore, RequestContext
from .fte import create_agent
from .services.content_loader import load_lesson_content

logger = logging.getLogger(__name__)

# Agent configuration
MAX_RECENT_ITEMS = 30
TITLE_MAX_WORDS = 6
TITLE_MAX_CHARS = 50


def _generate_thread_title(user_text: str) -> str:
    """Generate thread title from first few words of user message."""
    # Take first few words
    words = user_text.split()[:TITLE_MAX_WORDS]
    title = " ".join(words)

    # Truncate if too long
    if len(title) > TITLE_MAX_CHARS:
        title = title[:TITLE_MAX_CHARS - 3] + "..."

    # Add ellipsis if we truncated words
    if len(words) < len(user_text.split()):
        if not title.endswith("..."):
            title += "..."

    return title or "New Chat"


def _user_message_text(item: UserMessageItem) -> str:
    """Extract text from user message item."""
    parts: list[str] = []
    for part in item.content:
        if isinstance(part, UserMessageTextContent):
            parts.append(part.text)
    return " ".join(parts).strip()


class StudyModeChatKitServer(ChatKitServer[RequestContext]):
    """
    ChatKit server for Study Mode.

    This server handles read-only operations (items.list, threads.list, etc.)
    automatically via the base ChatKit server, and only uses custom logic
    for agent-triggering operations (threads.create, threads.run).
    """

    def __init__(self, store: CachedPostgresStore | PostgresStore):
        """Initialize the ChatKit server with PostgreSQL store."""
        super().__init__(store)
        logger.info("[ChatKit] StudyModeChatKitServer initialized")

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: RequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        Generate response for user message using Study Mode agent.

        Args:
            thread: Thread metadata
            input_user_message: User's message (None for retry scenarios)
            context: Request context with user_id

        Yields:
            ThreadStreamEvent: Stream of chat events
        """
        # For read-only operations, base ChatKit server handles them
        if not input_user_message:
            logger.info(
                "[ChatKit] No user message - this is likely a read-only operation"
            )
            return

        try:
            # Extract user message
            user_text = _user_message_text(input_user_message)
            if not user_text:
                logger.warning("[ChatKit] Empty user message")
                return

            # Get metadata from context
            lesson_path = context.metadata.get("lesson_path", "")
            mode = context.metadata.get("mode", "teach")
            user_name = context.metadata.get("user_name")

            logger.info(
                f"[ChatKit] Processing: user={context.user_id}, "
                f"lesson={lesson_path}, mode={mode}"
            )

            # Load lesson content
            content_data = await load_lesson_content(lesson_path)
            content = content_data.get("content", "")
            title = content_data.get("title", "Unknown")
            cached = content_data.get("cached", False)

            logger.info(
                f"[ChatKit] Content: title='{title}', "
                f"len={len(content)}, cached={cached}"
            )

            if not content:
                logger.warning(f"[ChatKit] No content for: {lesson_path}")

            # Create agent from orchestrator
            agent = create_agent(title, content, mode, user_name=user_name)

            # Get previous messages from thread for context
            previous_items = await self.store.load_thread_items(
                thread.id,
                after=None,
                limit=MAX_RECENT_ITEMS,
                order="desc",
                context=context,
            )
            items = list(reversed(previous_items.data))

            # Set thread title from first user message (if new thread)
            # Note: items will have 1 item (current user message) for new threads
            # because base ChatKitServer adds the message before calling respond()
            if len(items) <= 1 and "title" not in context.metadata:
                context.metadata["title"] = _generate_thread_title(user_text)
                logger.info(f"[ChatKit] Generated title: {context.metadata['title']}")
                # Save thread again with the generated title (base class saved with default)
                await self.store.save_thread(thread, context)

            # Convert to agent input format
            input_items = await simple_to_agent_input(items)

            # Fallback: if input_items is empty (race condition), use current user message
            if not input_items:
                logger.warning(
                    f"[ChatKit] Empty input_items for thread {thread.id}, "
                    f"using current user message as fallback"
                )
                input_items = user_text  # Agent SDK accepts string input

            # Create agent context
            agent_context = AgentContext(
                thread=thread,
                store=self.store,
                request_context=context,
            )

            # Run agent with streaming
            logger.info(f"[ChatKit] Running agent for thread {thread.id}")
            result = Runner.run_streamed(agent, input_items, context=agent_context)

            async for event in stream_agent_response(agent_context, result):
                yield event

            logger.info(f"[ChatKit] Response completed for thread {thread.id}")

        except Exception as e:
            logger.exception(f"[ChatKit] Error in respond(): {e}")

            # Send error message to client
            error_message = AssistantMessageItem(
                id=self.store.generate_item_id("message", thread, context),
                thread_id=thread.id,
                created_at=datetime.now(),
                content=[
                    AssistantMessageContent(
                        text=(
                            "I apologize, but I encountered an error. "
                            "Please try again."
                        ),
                        annotations=[],
                    )
                ],
            )
            yield ThreadItemDoneEvent(item=error_message)


def create_chatkit_server(
    store: CachedPostgresStore | PostgresStore,
) -> StudyModeChatKitServer:
    """Create a configured Study Mode ChatKit server instance."""
    return StudyModeChatKitServer(store)
