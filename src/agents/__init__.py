"""Sub-agent orchestration package.

Usage:
    from src.agents import AgentRegistry, Orchestrator, AgentTask, KillSwitch

Quick start:
    registry = AgentRegistry()
    ks       = KillSwitch(registry)
    orch     = Orchestrator(registry, ks)

    task = AgentTask(name="summarise", owner="main", input={"text": "..."})
    result = await orch.run(task)

Kill switch:
    ks.trigger("summarise")    # stop one agent
    ks.trigger_all()           # emergency stop — halts entire pipeline

See orchestrator.py for full API.
"""

from .kill_switch import KillSwitch
from .orchestrator import Orchestrator
from .registry import AgentRegistry, AgentRecord, AgentStatus
from .task import AgentHandoff, AgentResult, AgentTask

__all__ = [
    "AgentRegistry",
    "AgentRecord",
    "AgentStatus",
    "AgentTask",
    "AgentResult",
    "AgentHandoff",
    "Orchestrator",
    "KillSwitch",
]
