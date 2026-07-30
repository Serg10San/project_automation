"""Typed task, result, and handoff schemas for sub-agent communication.

Using dataclasses with explicit types prevents silent data loss when
one agent passes work to another.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentTask:
    """Payload passed to a sub-agent at launch time."""

    name: str
    owner: str
    input: dict[str, Any]
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout_seconds: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Structured result returned when a sub-agent completes."""

    task_id: str
    agent_id: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tokens_used: Optional[int] = None


@dataclass
class AgentHandoff:
    """Typed schema for passing work from one agent to the next.

    Never pass raw dicts between agents — use this schema so the
    receiving agent knows exactly what it is getting.
    """

    from_agent: str
    to_agent: str
    task: AgentTask
    context: dict[str, Any] = field(default_factory=dict)
    handoff_id: str = field(default_factory=lambda: str(uuid.uuid4()))
