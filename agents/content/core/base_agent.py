"""
BaseAgent
=========
Abstract base class for all OpenClaw Content Department agents.

Handles:
  - Redis event publishing (via aioredis / redis-py async)
  - Periodic heartbeat emission
  - Structured logging with trace context
  - Tool registry and sequential execution
  - Graceful shutdown on SIGTERM / SIGINT

Usage
-----
Subclass BaseAgent and implement `run_cycle()`.  Then call `agent.start()`.

    class ContentStrategistAgent(BaseAgent):
        async def run_cycle(self) -> None:
            trends = await self.run_tool("trend_scanner")
            briefs = await self.run_tool("brief_generator", trends=trends)
            for brief in briefs:
                await self.emit("content_briefs_ready", brief.redis_payload())
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import traceback
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as aioredis
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("openclaw.agents.base")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic config models
# ─────────────────────────────────────────────────────────────────────────────

class RedisConfig(BaseModel):
    """Redis connection parameters loaded from environment / config.yaml."""
    host: str       = Field(default="localhost")
    port: int       = Field(default=6379)
    db:   int       = Field(default=0)
    password: Optional[str] = None
    ssl: bool       = Field(default=False)
    socket_timeout: Optional[float] = Field(default=None)
    max_connections: int    = Field(default=10)

    @property
    def url(self) -> str:
        scheme   = "rediss" if self.ssl else "redis"
        password = f":{self.password}@" if self.password else ""
        return f"{scheme}://{password}{self.host}:{self.port}/{self.db}"


class AgentConfig(BaseModel):
    """Runtime configuration for a single agent instance."""
    agent_id:   str = Field(default_factory=lambda: f"agent-{uuid.uuid4().hex[:8]}")
    agent_name: str = Field(..., description="Human-readable name, e.g. 'ContentStrategist'")
    redis:      RedisConfig = Field(default_factory=RedisConfig)

    # Heartbeat
    heartbeat_interval_seconds: float = Field(
        default=30.0,
        description="How often to emit a heartbeat to Redis Pub/Sub"
    )
    heartbeat_channel: str = Field(
        default="openclaw:agents:heartbeats",
        description="Redis channel monitored by the dashboard / watchdog"
    )

    # Retry / resilience
    max_tool_retries: int   = Field(default=3)
    retry_backoff_seconds: float = Field(default=2.0)


# ─────────────────────────────────────────────────────────────────────────────
# Heartbeat payload
# ─────────────────────────────────────────────────────────────────────────────

class HeartbeatPayload(BaseModel):
    agent_id:    str
    agent_name:  str
    status:      str    # "idle" | "running" | "error"
    cycle_count: int
    last_error:  Optional[str] = None
    timestamp:   str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool wrapper
# ─────────────────────────────────────────────────────────────────────────────

ToolFn = Callable[..., Coroutine[Any, Any, Any]]


class ToolRegistration(BaseModel):
    """Internal registry entry for an agent tool."""
    name: str
    fn: Any  # ToolFn — left as Any to avoid Pydantic coercion
    description: str = ""

    model_config = {"arbitrary_types_allowed": True}


# ─────────────────────────────────────────────────────────────────────────────
# BaseAgent
# ─────────────────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base for all OpenClaw Content Department agents.

    Lifecycle
    ---------
    1. `__init__`       → Store config, initialise state.
    2. `start()`        → Open Redis, launch heartbeat task, enter main loop.
    3. `run_cycle()`    → Implemented by each concrete agent; called repeatedly.
    4. `stop()`         → Graceful shutdown: cancel tasks, close Redis.

    Redis Contract
    --------------
    Events are published as JSON to Redis Pub/Sub channels following the naming
    convention  ``openclaw:events:<event_name>``.

    Example channels:
        openclaw:events:content_briefs_ready
        openclaw:events:post_published
        openclaw:events:audit_complete
    """

    # Class-level channel prefix — override per agent if needed
    EVENT_CHANNEL_PREFIX: str = "openclaw:events"

    def __init__(self, config: AgentConfig) -> None:
        self.config       = config
        self.agent_id     = config.agent_id
        self.agent_name   = config.agent_name

        self._redis:           Optional[aioredis.Redis]       = None
        self._heartbeat_task:  Optional[asyncio.Task]         = None
        self._main_loop_task:  Optional[asyncio.Task]         = None

        self._running:    bool = False
        self._cycle_count: int = 0
        self._last_error:  Optional[str] = None

        self._tool_registry: dict[str, ToolRegistration] = {}

        self._log = logging.getLogger(
            f"openclaw.agents.{self.agent_name.lower().replace(' ', '_')}"
        )

    # ── Tool Registry ──────────────────────────────────────────────────────

    def register_tool(
        self,
        name: str,
        fn: ToolFn,
        description: str = ""
    ) -> None:
        """Register a callable tool by name. Call this in `__init__` of subclasses."""
        self._tool_registry[name] = ToolRegistration(
            name=name, fn=fn, description=description
        )
        self._log.debug("Registered tool: %s", name)

    async def run_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Execute a registered tool with retry logic.

        Retries up to ``config.max_tool_retries`` times with exponential
        back-off of ``config.retry_backoff_seconds``.

        Parameters
        ----------
        tool_name : str
            The name under which the tool was registered.
        **kwargs
            Passed directly to the tool coroutine.

        Returns
        -------
        Any
            Whatever the tool coroutine returns.

        Raises
        ------
        KeyError
            If the tool is not registered.
        Exception
            Re-raised if all retries are exhausted.
        """
        if tool_name not in self._tool_registry:
            raise KeyError(
                f"[{self.agent_name}] Tool '{tool_name}' is not registered. "
                f"Available: {list(self._tool_registry.keys())}"
            )

        registration = self._tool_registry[tool_name]
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.config.max_tool_retries + 1):
            try:
                self._log.info(
                    "Running tool '%s' (attempt %d/%d)",
                    tool_name, attempt, self.config.max_tool_retries
                )
                result = await registration.fn(**kwargs)
                self._log.info("Tool '%s' succeeded.", tool_name)
                return result
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                backoff = self.config.retry_backoff_seconds * (2 ** (attempt - 1))
                self._log.warning(
                    "Tool '%s' failed (attempt %d): %s. Retrying in %.1fs…",
                    tool_name, attempt, exc, backoff
                )
                await asyncio.sleep(backoff)

        self._log.error(
            "Tool '%s' exhausted all %d retries. Last error: %s",
            tool_name, self.config.max_tool_retries, last_exc
        )
        raise last_exc  # type: ignore[misc]

    # ── Redis helpers ──────────────────────────────────────────────────────

    async def _connect_redis(self) -> None:
        """Open an async Redis connection pool."""
        self._redis = aioredis.from_url(
            self.config.redis.url,
            max_connections=self.config.redis.max_connections,
            socket_timeout=self.config.redis.socket_timeout,
            decode_responses=True,
        )
        await self._redis.ping()
        self._log.info("Redis connected: %s", self.config.redis.url)

    async def emit(
        self,
        event_name: str,
        payload: dict[str, Any],
        *,
        channel_override: Optional[str] = None,
    ) -> int:
        """
        Publish a JSON-encoded event to a Redis Pub/Sub channel.

        Parameters
        ----------
        event_name : str
            Short event name, e.g. ``"content_briefs_ready"``.
            Full channel becomes ``openclaw:events:<event_name>``.
        payload : dict
            Must be JSON-serialisable.
        channel_override : str, optional
            Publish to an explicit channel name instead of the default prefix.

        Returns
        -------
        int
            Number of subscribers that received the message.
        """
        if self._redis is None:
            raise RuntimeError(
                f"[{self.agent_name}] Redis is not connected. Call start() first."
            )

        channel = channel_override or f"{self.EVENT_CHANNEL_PREFIX}:{event_name}"

        envelope = {
            "event":      event_name,
            "agent_id":   self.agent_id,
            "agent_name": self.agent_name,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "payload":    payload,
        }

        serialised = json.dumps(envelope, default=str)
        receivers: int = await self._redis.publish(channel, serialised)

        self._log.info(
            "Event '%s' published to '%s' -> %d receiver(s).",
            event_name, channel, receivers
        )
        return receivers

    async def subscribe(
        self,
        event_name: str,
        handler: Callable[[dict], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Subscribe to a Redis Pub/Sub channel and dispatch messages to ``handler``.

        This method runs indefinitely; run it as an ``asyncio.Task``.

        Parameters
        ----------
        event_name : str
            Short event name (same format as used in ``emit``).
        handler : async callable
            Receives the full envelope dict for each message.
        """
        if self._redis is None:
            raise RuntimeError("Redis is not connected.")

        channel = f"{self.EVENT_CHANNEL_PREFIX}:{event_name}"
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        self._log.info("Subscribed to channel: %s", channel)

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    envelope = json.loads(message["data"])
                    await handler(envelope)
                except json.JSONDecodeError as exc:
                    self._log.error("Malformed message on %s: %s", channel, exc)
                except Exception as exc:  # noqa: BLE001
                    self._log.exception("Handler error on %s: %s", channel, exc)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    # ── Heartbeat ──────────────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """
        Emit a heartbeat to Redis every ``heartbeat_interval_seconds`` seconds.

        The heartbeat payload is published to ``heartbeat_channel`` so that
        the OpenClaw dashboard and watchdog service can detect stale agents
        and trigger alerts or automatic restarts.
        """
        self._log.debug(
            "Heartbeat loop started (interval=%.1fs, channel=%s)",
            self.config.heartbeat_interval_seconds,
            self.config.heartbeat_channel,
        )

        while self._running:
            status = "running" if self._cycle_count > 0 else "idle"
            hb = HeartbeatPayload(
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                status=status,
                cycle_count=self._cycle_count,
                last_error=self._last_error,
            )

            try:
                if self._redis:
                    await self._redis.publish(
                        self.config.heartbeat_channel,
                        hb.model_dump_json(),
                    )
                    self._log.debug(
                        "Heartbeat sent (cycle=%d, status=%s)",
                        self._cycle_count, status
                    )
            except Exception as exc:  # noqa: BLE001
                self._log.warning("Heartbeat publish failed: %s", exc)

            await asyncio.sleep(self.config.heartbeat_interval_seconds)

    # ── Main Loop ──────────────────────────────────────────────────────────

    @abstractmethod
    async def run_cycle(self) -> None:
        """
        Core agent logic — implemented by each concrete agent.

        This method is called on every scheduled tick.  It should:
          1. Call registered tools via ``self.run_tool(…)``
          2. Emit Redis events via ``self.emit(…)``
          3. Write results to PostgreSQL via SQLAlchemy sessions

        Any unhandled exception will be caught by the main loop,
        logged with a full traceback, and the agent will back off
        before the next cycle.
        """
        ...

    async def _main_loop(self, cycle_interval_seconds: float) -> None:
        """Schedule repeated calls to ``run_cycle``."""
        self._log.info(
            "Main loop started (cycle_interval=%.1fs)", cycle_interval_seconds
        )

        while self._running:
            try:
                cycle_start = asyncio.get_event_loop().time()
                self._log.info(
                    "=== [%s] Cycle #%d starting ===",
                    self.agent_name, self._cycle_count + 1
                )

                await self.run_cycle()

                self._cycle_count += 1
                self._last_error = None
                elapsed = asyncio.get_event_loop().time() - cycle_start
                self._log.info(
                    "=== [%s] Cycle #%d completed in %.2fs ===",
                    self.agent_name, self._cycle_count, elapsed
                )

            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self._last_error = traceback.format_exc()
                self._log.exception(
                    "[%s] Unhandled exception in run_cycle: %s", self.agent_name, exc
                )
                # Emit an error event so the dashboard can react
                try:
                    await self.emit("agent_error", {
                        "agent_id":   self.agent_id,
                        "agent_name": self.agent_name,
                        "cycle":      self._cycle_count,
                        "error":      str(exc),
                        "traceback":  self._last_error,
                    })
                except Exception:  # noqa: BLE001
                    pass  # Silent — don't let error reporting crash the agent

            # Sleep until the next cycle (subtract elapsed time for precision)
            await asyncio.sleep(cycle_interval_seconds)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def start(self, cycle_interval_seconds: float = 14_400.0) -> None:
        """
        Start the agent.

        Parameters
        ----------
        cycle_interval_seconds : float
            Seconds between ``run_cycle`` calls.
            Defaults to 14 400 (4 hours — matches Agent 01's cron cadence).
            Agent 02 should pass 7200 (2 hours).
        """
        self._log.info(
            "Starting agent '%s' (id=%s) …", self.agent_name, self.agent_id
        )
        self._running = True

        # Connect to Redis
        await self._connect_redis()

        # Register OS signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(self.stop()))

        # Launch background tasks
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name=f"{self.agent_name}-heartbeat"
        )
        self._main_loop_task = asyncio.create_task(
            self._main_loop(cycle_interval_seconds),
            name=f"{self.agent_name}-main-loop"
        )

        await self.emit("agent_started", {
            "agent_id":   self.agent_id,
            "agent_name": self.agent_name,
            "cycle_interval_seconds": cycle_interval_seconds,
        })

        self._log.info("Agent '%s' is running.", self.agent_name)

        # Block until main loop finishes (cancelled on stop())
        try:
            await self._main_loop_task
        except asyncio.CancelledError:
            self._log.info("Main loop task cancelled for '%s'.", self.agent_name)

    async def stop(self) -> None:
        """Gracefully shut down the agent."""
        self._log.info("Stopping agent '%s' …", self.agent_name)
        self._running = False

        await self.emit("agent_stopped", {
            "agent_id":   self.agent_id,
            "agent_name": self.agent_name,
            "cycles_completed": self._cycle_count,
        })

        for task in (self._heartbeat_task, self._main_loop_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._redis:
            await self._redis.aclose()
            self._log.info("Redis connection closed.")

        self._log.info(
            "Agent '%s' stopped after %d cycle(s).",
            self.agent_name, self._cycle_count
        )
