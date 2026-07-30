"""Orchestrator — launches sub-agents, collects results, enforces safety.

The orchestrator is the single entry point for running sub-agents.
It handles:
    - Kill-switch checks before launch
    - Agent registration and lifecycle tracking
    - Async execution with optional timeout
    - Circuit breaker: halts pipeline if failure rate exceeds threshold
    - Structured handoffs between sequential agents

Usage:
    registry = AgentRegistry()
    ks       = KillSwitch(registry)
    orch     = Orchestrator(registry, ks, failure_threshold=0.5)

    async def my_agent(task: AgentTask, ks: KillSwitch) -> AgentResult:
        if ks.is_killed(task.task_id):
            return AgentResult(task_id=task.task_id, agent_id=task.task_id,
                               success=False, error="killed")
        # ... do work ...
        return AgentResult(task_id=task.task_id, agent_id=task.task_id,
                           success=True, output={"answer": "..."})

    result = await orch.run(task, handler=my_agent)
    results = await orch.run_parallel([task1, task2], handler=my_agent)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Callable, Awaitable

from .kill_switch import KillSwitch
from .registry import AgentRegistry
from .task import AgentHandoff, AgentResult, AgentTask

AgentHandler = Callable[[AgentTask, KillSwitch], Awaitable[AgentResult]]


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker has tripped."""


class Orchestrator:
    def __init__(
        self,
        registry: AgentRegistry,
        kill_switch: KillSwitch,
        failure_threshold: float = 0.5,
    ) -> None:
        self._registry = registry
        self._ks = kill_switch
        self._failure_threshold = failure_threshold
        self._results: list[AgentResult] = []

    # ── Single agent ──────────────────────────────────────────────────────────

    async def run(self, task: AgentTask, handler: AgentHandler) -> AgentResult:
        if self._ks.is_all_killed():
            raise CircuitBreakerOpen("Global kill switch is active.")

        self._check_circuit_breaker()

        agent_id = str(uuid.uuid4())
        self._registry.register(agent_id=agent_id, name=task.name, owner=task.owner)
        self._registry.mark_running(agent_id)

        try:
            if task.timeout_seconds:
                coro = handler(task, self._ks)
                result = await asyncio.wait_for(coro, timeout=task.timeout_seconds)
            else:
                result = await handler(task, self._ks)

            if result.success:
                self._registry.mark_done(agent_id)
            else:
                self._registry.mark_failed(agent_id, result.error or "unknown")

        except asyncio.TimeoutError:
            self._registry.mark_failed(agent_id, "timeout")
            result = AgentResult(
                task_id=task.task_id, agent_id=agent_id,
                success=False, error="timeout"
            )
        except Exception as exc:
            self._registry.mark_failed(agent_id, str(exc))
            result = AgentResult(
                task_id=task.task_id, agent_id=agent_id,
                success=False, error=str(exc)
            )

        self._results.append(result)
        return result

    # ── Parallel agents ───────────────────────────────────────────────────────

    async def run_parallel(
        self, tasks: list[AgentTask], handler: AgentHandler
    ) -> list[AgentResult]:
        self._check_circuit_breaker()
        coroutines = [self.run(task, handler) for task in tasks]
        return list(await asyncio.gather(*coroutines, return_exceptions=False))

    # ── Handoff ───────────────────────────────────────────────────────────────

    async def handoff(
        self,
        handoff: AgentHandoff,
        handler: AgentHandler,
    ) -> AgentResult:
        """Execute the next agent in a sequential pipeline via typed handoff."""
        task = AgentTask(
            name=handoff.task.name,
            owner=handoff.from_agent,
            input={**handoff.task.input, **handoff.context},
            timeout_seconds=handoff.task.timeout_seconds,
        )
        return await self.run(task, handler)

    # ── Circuit breaker ───────────────────────────────────────────────────────

    def _check_circuit_breaker(self) -> None:
        if not self._results:
            return
        failures = sum(1 for r in self._results if not r.success)
        rate = failures / len(self._results)
        if rate >= self._failure_threshold:
            self._ks.trigger_all()
            raise CircuitBreakerOpen(
                f"Circuit breaker tripped: {rate:.0%} failure rate "
                f"(threshold {self._failure_threshold:.0%})."
            )
