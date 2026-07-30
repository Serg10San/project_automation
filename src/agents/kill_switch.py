"""Kill switch — emergency stop for individual agents or the entire pipeline.

Contract:
    - Any agent MUST check ks.is_killed(agent_id) at the start of each
      major step and abort cleanly if True.
    - trigger_all() sets a global flag; all agents must honour it.
    - The orchestrator checks is_all_killed() before launching new agents.

Usage:
    ks = KillSwitch(registry)
    ks.trigger("agent-abc")       # stop one agent
    ks.trigger_all()              # emergency stop — halt everything
    ks.is_killed("agent-abc")     # True if targeted or global kill active
    ks.reset("agent-abc")         # clear a single kill (for retry)
    ks.reset_all()                # clear global kill (operator action)
"""

from __future__ import annotations

import threading

from .registry import AgentRegistry


class KillSwitch:
    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry
        self._lock = threading.Lock()
        self._killed: set[str] = set()
        self._global_kill = False

    def trigger(self, agent_id: str) -> None:
        with self._lock:
            self._killed.add(agent_id)
        self._registry.mark_killed(agent_id)

    def trigger_all(self) -> None:
        with self._lock:
            self._global_kill = True
        for record in self._registry.active_agents():
            self._registry.mark_killed(record.agent_id)

    def is_killed(self, agent_id: str) -> bool:
        with self._lock:
            return self._global_kill or agent_id in self._killed

    def is_all_killed(self) -> bool:
        with self._lock:
            return self._global_kill

    def reset(self, agent_id: str) -> None:
        with self._lock:
            self._killed.discard(agent_id)

    def reset_all(self) -> None:
        with self._lock:
            self._killed.clear()
            self._global_kill = False
