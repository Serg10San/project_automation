"""Agent registry — tracks every active sub-agent by ID.

Every agent must register before it runs and deregister when it finishes.
This gives the kill switch and the audit log a single source of truth.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    KILLED = "killed"


@dataclass
class AgentRecord:
    agent_id: str
    name: str
    owner: str
    status: AgentStatus = AgentStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


class AgentRegistry:
    """Thread-safe registry of active and historical agents."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._agents: dict[str, AgentRecord] = {}

    def register(self, agent_id: str, name: str, owner: str) -> AgentRecord:
        record = AgentRecord(agent_id=agent_id, name=name, owner=owner)
        with self._lock:
            self._agents[agent_id] = record
        return record

    def mark_running(self, agent_id: str) -> None:
        with self._lock:
            record = self._agents[agent_id]
            record.status = AgentStatus.RUNNING
            record.started_at = datetime.now(timezone.utc)

    def mark_done(self, agent_id: str) -> None:
        with self._lock:
            record = self._agents[agent_id]
            record.status = AgentStatus.DONE
            record.finished_at = datetime.now(timezone.utc)

    def mark_failed(self, agent_id: str, error: str) -> None:
        with self._lock:
            record = self._agents[agent_id]
            record.status = AgentStatus.FAILED
            record.finished_at = datetime.now(timezone.utc)
            record.error = error

    def mark_killed(self, agent_id: str) -> None:
        with self._lock:
            record = self._agents[agent_id]
            record.status = AgentStatus.KILLED
            record.finished_at = datetime.now(timezone.utc)

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        with self._lock:
            return self._agents.get(agent_id)

    def active_agents(self) -> list[AgentRecord]:
        with self._lock:
            return [r for r in self._agents.values() if r.status == AgentStatus.RUNNING]

    def all_agents(self) -> list[AgentRecord]:
        with self._lock:
            return list(self._agents.values())
