"""Redis-cached PostgreSQL store for ChatKit.

This implements a write-through cache pattern:
- Writes go to PostgreSQL + Redis
- Reads try Redis first, fallback to PostgreSQL
- Cache invalidation on updates/deletes

Adapted from carfixer-agents-agentkit for Study Mode API.
"""

import asyncio
import json
import logging
from typing import Any

from chatkit.types import Page, ThreadItem, ThreadMetadata

from .context import RequestContext
from .postgres_store import ItemData, PostgresStore, ThreadData

logger = logging.getLogger(__name__)


class CachedPostgresStore(PostgresStore):
    """
    PostgreSQL store with Redis caching layer.

    Caching Strategy:
    - Thread metadata: Cache for 1 hour
    - Thread items: Cache for 30 minutes
    - Thread lists: Cache for 10 minutes

    Cache Keys:
    - chatkit:thread:{user_id}:{thread_id} -> ThreadMetadata
    - chatkit:items:{user_id}:{thread_id}:{limit}:{order} -> Page[ThreadItem]
    - chatkit:threads:{user_id}:{limit}:{order} -> Page[ThreadMetadata]
    """

    def __init__(
        self,
        *args,
        redis_client=None,
        **kwargs,
    ):
        """
        Initialize cached store.

        Args:
            redis_client: Optional Redis client. If None, caching is disabled.
        """
        super().__init__(*args, **kwargs)
        self.redis = redis_client
        self.cache_enabled = redis_client is not None

        # Cache TTLs in seconds
        self.thread_ttl = 3600  # 1 hour
        self.items_ttl = 1800  # 30 minutes
        self.list_ttl = 600  # 10 minutes

        # Background write queue for async database operations
        self._background_writes: asyncio.Queue[tuple[Any, ...]] = asyncio.Queue(
            maxsize=1000
        )
        self._background_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._queue_full_warnings = 0

        if self.cache_enabled:
            logger.info("Redis caching enabled for PostgresStore")
        else:
            logger.warning("Redis caching disabled - no Redis client provided")

    async def start_background_writer(self) -> None:
        """Start the background writer task."""
        if self._background_task is None:
            self._background_task = asyncio.create_task(self._background_write_worker())
            logger.info("Background writer started")

    async def stop_background_writer(self) -> None:
        """Stop the background writer task gracefully."""
        if self._background_task:
            self._shutdown_event.set()
            await self._background_task
            self._background_task = None
            logger.info("Background writer stopped")

    async def _background_write_worker(self) -> None:
        """Background worker that processes database writes."""
        logger.info("Background write worker started")

        while not self._shutdown_event.is_set():
            try:
                write_task = await asyncio.wait_for(
                    self._background_writes.get(), timeout=1.0
                )

                operation, args, kwargs = write_task
                start_time = asyncio.get_event_loop().time()

                try:
                    await operation(*args, **kwargs)
                    duration = asyncio.get_event_loop().time() - start_time
                    logger.debug(
                        f"Background write done in {duration * 1000:.1f}ms: "
                        f"{operation.__name__}"
                    )
                except Exception as e:
                    logger.error(f"Background write failed: {operation.__name__}: {e}")

                self._background_writes.task_done()

            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Background writer error: {e}")

        logger.info("Background write worker stopped")

    async def _queue_background_write(
        self, operation: Any, *args: Any, **kwargs: Any
    ) -> None:
        """Queue a database write operation for background execution."""
        if self._background_task is None:
            await self.start_background_writer()

        queue_size = self._background_writes.qsize()
        if queue_size > 800:
            self._queue_full_warnings += 1
            if self._queue_full_warnings % 10 == 1:
                logger.warning(
                    f"Background write queue is {queue_size}/1000 - system under heavy load"
                )

        try:
            await asyncio.wait_for(
                self._background_writes.put((operation, args, kwargs)), timeout=5.0
            )
            logger.debug(f"Queued background write: {operation.__name__}")
        except TimeoutError:
            logger.error(
                f"Failed to queue background write: {operation.__name__} - queue full, "
                f"falling back to synchronous write"
            )
            await operation(*args, **kwargs)

    def _get_thread_cache_key(self, user_id: str, thread_id: str) -> str:
        """Generate cache key for thread metadata."""
        return f"chatkit:thread:{user_id}:{thread_id}"

    def _get_items_cache_key(
        self, user_id: str, thread_id: str, limit: int, order: str
    ) -> str:
        """Generate cache key for thread items."""
        return f"chatkit:items:{user_id}:{thread_id}:{limit}:{order}"

    def _get_list_cache_key(self, user_id: str, limit: int, order: str) -> str:
        """Generate cache key for thread list."""
        return f"chatkit:threads:{user_id}:{limit}:{order}"

    async def _get_cached(self, key: str) -> dict | None:
        """Get cached value from Redis."""
        if not self.cache_enabled:
            return None

        try:
            value = await self.redis.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            return None

    async def _set_cached(self, key: str, value: dict, ttl: int) -> None:
        """Set cached value in Redis with TTL."""
        if not self.cache_enabled:
            return

        try:
            await self.redis.setex(
                key,
                ttl,
                json.dumps(value, default=str),
            )
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"Redis set error for key {key}: {e}")

    async def _delete_cached(self, key: str) -> None:
        """Delete cached value from Redis."""
        if not self.cache_enabled:
            return

        try:
            await self.redis.delete(key)
            logger.debug(f"Cache DELETE: {key}")
        except Exception as e:
            logger.warning(f"Redis delete error for key {key}: {e}")

    async def _delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a pattern using SCAN."""
        if not self.cache_enabled:
            return

        try:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"Pattern delete error for {pattern}: {e}")

    async def _invalidate_thread_cache(self, user_id: str, thread_id: str) -> None:
        """Invalidate all cache entries related to a thread."""
        if not self.cache_enabled:
            return

        try:
            await self._delete_cached(self._get_thread_cache_key(user_id, thread_id))
            await self._delete_pattern(f"chatkit:items:{user_id}:{thread_id}:*")
            await self._delete_pattern(f"chatkit:threads:{user_id}:*")
            logger.debug(f"Invalidated cache for thread {thread_id}")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

    # Override PostgresStore methods with caching

    async def load_thread(
        self, thread_id: str, context: RequestContext
    ) -> ThreadMetadata:
        """Load thread with Redis caching."""
        cache_key = self._get_thread_cache_key(context.user_id, thread_id)

        cached = await self._get_cached(cache_key)
        if cached:
            return ThreadData.model_validate(cached).thread

        thread = await super().load_thread(thread_id, context)

        await self._set_cached(
            cache_key, ThreadData(thread=thread).model_dump(), self.thread_ttl
        )

        return thread

    async def save_thread(
        self, thread: ThreadMetadata, context: RequestContext
    ) -> None:
        """Save thread to DB and update cache (write-through)."""
        await super().save_thread(thread, context)

        cache_key = self._get_thread_cache_key(context.user_id, thread.id)
        await self._set_cached(
            cache_key, ThreadData(thread=thread).model_dump(), self.thread_ttl
        )

        # Invalidate thread lists only
        await self._delete_pattern(f"chatkit:threads:{context.user_id}:*")

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadItem]:
        """Load thread items with Redis caching."""
        # Only cache if no pagination cursor
        if after is None:
            cache_key = self._get_items_cache_key(
                context.user_id, thread_id, limit, order
            )

            cached = await self._get_cached(cache_key)
            if cached:
                items = [
                    ItemData.model_validate(item_dict).item
                    for item_dict in cached.get("data", [])
                ]
                return Page[ThreadItem](
                    data=items,
                    has_more=cached.get("has_more", False),
                    after=cached.get("after"),
                )

        page = await super().load_thread_items(thread_id, after, limit, order, context)

        if after is None:
            cache_key = self._get_items_cache_key(
                context.user_id, thread_id, limit, order
            )
            await self._set_cached(
                cache_key,
                {
                    "data": [ItemData(item=item).model_dump() for item in page.data],
                    "has_more": page.has_more,
                    "after": page.after,
                },
                self.items_ttl,
            )

        return page

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        """Add item using background writer for faster response."""
        await self._queue_background_write(
            super().add_thread_item, thread_id, item, context
        )

        await self._queue_background_write(
            self._update_items_cache_after_add, thread_id, item, context
        )

    async def _update_items_cache_after_add(
        self, thread_id: str, new_item: ThreadItem, context: RequestContext
    ) -> None:
        """Update cached items pages by adding the new item."""
        if not self.cache_enabled:
            return

        try:
            pattern = f"chatkit:items:{context.user_id}:{thread_id}:*"
            cursor = 0
            cache_keys = []

            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                cache_keys.extend(keys)
                if cursor == 0:
                    break

            for cache_key in cache_keys:
                try:
                    cached_data = await self.redis.get(cache_key)
                    if not cached_data:
                        continue

                    page_data = json.loads(cached_data)
                    items_list = page_data.get("data", [])

                    new_item_data = ItemData(item=new_item).model_dump()
                    if ":desc" in cache_key:
                        items_list.insert(0, new_item_data)
                    else:
                        items_list.append(new_item_data)

                    page_data["data"] = items_list

                    ttl = await self.redis.ttl(cache_key)
                    if ttl > 0:
                        await self.redis.setex(
                            cache_key, ttl, json.dumps(page_data, default=str)
                        )
                        logger.debug(f"Updated cache page: {cache_key}")

                except Exception as e:
                    logger.warning(f"Failed to update cache page {cache_key}: {e}")
                    await self.redis.delete(cache_key)

        except Exception as e:
            logger.warning(f"Failed to update items cache: {e}")
            await self._delete_pattern(f"chatkit:items:{context.user_id}:{thread_id}:*")

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        """Update item and selectively refresh cache."""
        await super().save_item(thread_id, item, context)

        try:
            pattern = f"chatkit:items:{context.user_id}:{thread_id}:*"
            cursor = 0

            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor, match=pattern, count=100
                )

                for cache_key in keys:
                    ttl = await self.redis.ttl(cache_key)
                    # Only delete if cache is more than 5 minutes old
                    if ttl < (self.items_ttl - 300):
                        await self.redis.delete(cache_key)
                        logger.debug(f"Deleted old cache: {cache_key}")

                if cursor == 0:
                    break

        except Exception as e:
            logger.warning(f"Error in selective cache invalidation: {e}")
            await self._delete_pattern(f"chatkit:items:{context.user_id}:{thread_id}:*")

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> None:
        """Delete item and invalidate items cache."""
        await super().delete_thread_item(thread_id, item_id, context)

        pattern = f"chatkit:items:{context.user_id}:{thread_id}:*"
        await self._delete_pattern(pattern)

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadMetadata]:
        """Load threads with Redis caching."""
        if after is None:
            cache_key = self._get_list_cache_key(context.user_id, limit, order)

            cached = await self._get_cached(cache_key)
            if cached:
                threads = [
                    ThreadData.model_validate(thread_dict).thread
                    for thread_dict in cached.get("data", [])
                ]
                return Page[ThreadMetadata](
                    data=threads,
                    has_more=cached.get("has_more", False),
                    after=cached.get("after"),
                )

        page = await super().load_threads(limit, after, order, context)

        if after is None:
            cache_key = self._get_list_cache_key(context.user_id, limit, order)
            await self._set_cached(
                cache_key,
                {
                    "data": [
                        ThreadData(thread=thread).model_dump() for thread in page.data
                    ],
                    "has_more": page.has_more,
                    "after": page.after,
                },
                self.list_ttl,
            )

        return page

    async def delete_thread(self, thread_id: str, context: RequestContext) -> None:
        """Delete thread and invalidate all related caches."""
        await super().delete_thread(thread_id, context)
        await self._invalidate_thread_cache(context.user_id, thread_id)

    async def close(self) -> None:
        """Close the store and stop background tasks."""
        await self.stop_background_writer()
        await super().close()
