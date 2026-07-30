---
name: avoiding-agent-conflicts
description: >
  Multi-agent conflict prevention. Use when designing a new agent, reviewing an
  agent interaction, debugging a deadlock or duplicate-work scenario, or when
  the word "conflict", "overlap", "loop", or "deadlock" appears in the
  conversation. Covers: goal alignment, overlap avoidance, conflict blocking,
  activity monitoring, and safety fail-safes.
---

# Avoiding Agent Conflicts

When multiple agents operate in the same system they can produce **goal drift**
(misaligned objectives), **redundant work** (duplicate task execution),
**contradictory instructions** (blocking loops), and **deadlocks** (agents
waiting on one another indefinitely).  This skill prevents all four failure
modes using five interlocking practices.

---

## The Five Pillars

### 1. Goal Alignment Review

Before deploying any new agent, verify its objective fits the wider system.

**Check these questions:**

- [ ] Is the agent's stated objective consistent with the system's overall goal?
- [ ] Does the objective contradict any existing agent's objective?
- [ ] Is the objective bounded — does it have a clear *stop* condition?
- [ ] Is the agent registered in the agent manifest / registry?

**Pattern to add to every new agent:**

```python
# Every agent must declare its goal and stop condition at initialisation.
agent_manifest = {
    "agent_id": "unique-agent-id",
    "goal": "Single-sentence statement of what this agent achieves.",
    "stop_condition": "Condition under which this agent terminates normally.",
    "agent_owner": "team-or-person@example.com",
    "approved_actions": ["list", "of", "allowed", "actions"],
}
```

---

### 2. Avoidance of Overlap

Before assigning a task to an agent, check whether another agent already owns it.

**Where to look:**
- The shared task registry / queue
- In-flight task ledger (tasks currently being processed)
- Agent activity logs from the last N minutes

**Pattern — task claim with idempotency guard:**

```python
def claim_task(task_id: str, agent_id: str, registry) -> bool:
    """Return True only if this agent successfully claimed an unclaimed task."""
    if registry.is_claimed(task_id):
        return False  # another agent owns it — skip, do not duplicate
    registry.claim(task_id, agent_id)
    return True
```

**Rule:** An agent must *claim* a task atomically before starting work.
If the claim fails, the agent moves on — it never starts duplicate work.

---

### 3. Conflict Blocking

Detect and block instructions that contradict one another before execution.

**Three contradiction types to check:**

| Type | Example | Detection |
|------|---------|-----------|
| **Direct** | Agent A told to start X; Agent B told to stop X | Same resource, opposite verbs |
| **Scope** | Agent A owns resource R exclusively; Agent B tries to write R | Exclusive lock violation |
| **Ordering** | Agent A must run before B; B is scheduled before A | Dependency inversion |

**Pattern — instruction validator:**

```python
def validate_instruction(instruction, active_instructions: list) -> tuple[bool, str]:
    """Check instruction against all active instructions. Returns (ok, reason)."""
    for active in active_instructions:
        if instructions_conflict(instruction, active):
            return False, f"Conflicts with active instruction from {active['agent_id']}"
    return True, "ok"
```

**Rule:** Never execute an instruction that fails validation.  Log the
conflict and escalate — do not silently drop either instruction.

---

### 4. Monitoring

Continuously track agent activity to surface problems early.

**What to track (minimum viable monitoring):**

```python
# Emit on every agent action
audit_log.record({
    "agent_id":    agent_id,
    "action":      action_name,
    "task_id":     task_id,
    "timestamp":   utcnow(),
    "status":      "started" | "completed" | "failed",
})
```

**Alerts to configure:**

| Signal | Threshold | Meaning |
|--------|-----------|---------|
| Same task claimed by >1 agent | Any | Overlap / race condition |
| Agent hasn't emitted heartbeat | >2× expected interval | Agent stuck or deadlocked |
| Same task restarted >N times | N=3 | Retry loop — possible deadlock |
| Two agents blocked waiting on each other | Any | Classic deadlock |

**Deadlock detection pattern:**

```python
def detect_deadlock(wait_graph: dict[str, str]) -> list[str]:
    """Find agents in a circular wait.  wait_graph[a] = b means a waits on b."""
    visited, cycle = set(), []
    def dfs(node, path):
        if node in path:
            return path[path.index(node):]  # cycle found
        if node in visited or node not in wait_graph:
            return []
        visited.add(node)
        return dfs(wait_graph[node], path + [node])
    for agent in wait_graph:
        if result := dfs(agent, []):
            cycle = result
            break
    return cycle
```

---

### 5. Safety Fail-safes

Guarantee the system can always recover — even when agents misbehave.

**Required mechanisms:**

```python
# 1. Per-operation timeout — every agent action must time-bound itself.
async def run_with_timeout(coro, timeout_seconds: float):
    return await asyncio.wait_for(coro, timeout=timeout_seconds)

# 2. Kill switch — immediate halt for a specific agent or the whole fleet.
kill_switch_flags: dict[str, bool] = {}

def check_kill_switch(agent_id: str) -> None:
    if kill_switch_flags.get(agent_id) or kill_switch_flags.get("ALL"):
        raise AgentHaltException(f"Kill switch activated for {agent_id}")

# 3. Escalation path — when an agent can't resolve a conflict, page a human.
def escalate(agent_id: str, reason: str, context: dict) -> None:
    escalation_policy.notify(
        to=agent_manifest[agent_id]["agent_owner"],
        subject=f"Agent conflict escalation — {agent_id}",
        body=reason,
        context=context,
    )
```

**Circuit breaker** — stop retrying after N failures, allow cool-down:

```python
class AgentCircuitBreaker:
    def __init__(self, failure_threshold=5, cooldown_seconds=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.open_until: float | None = None

    def call(self, fn, *args, **kwargs):
        if self.open_until and time.time() < self.open_until:
            raise CircuitOpenError("Circuit breaker open — backing off")
        try:
            result = fn(*args, **kwargs)
            self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.open_until = time.time() + self.cooldown_seconds
            raise
```

---

## Workflow — New Agent Review Checklist

Run through this checklist every time a new agent is introduced:

```
GOAL ALIGNMENT
[ ] Agent has a documented goal and stop condition
[ ] Goal does not contradict any existing agent's goal
[ ] Agent is registered in the agent manifest

OVERLAP AVOIDANCE
[ ] Agent uses atomic task claiming before starting work
[ ] Task registry / queue is shared and visible to all agents

CONFLICT BLOCKING
[ ] Instruction validator is wired in before execution
[ ] Conflicting instructions are logged and escalated (not silently dropped)

MONITORING
[ ] Agent emits structured audit logs on every action
[ ] Heartbeat / liveness signal is configured
[ ] Duplicate-task and deadlock alerts are set up

SAFETY FAIL-SAFES
[ ] All async operations have timeouts
[ ] Kill switch is implemented and tested
[ ] Circuit breaker wraps all external/inter-agent calls
[ ] Escalation path routes to a named human owner
```

---

## When to invoke this skill

| Trigger phrase | What to do |
|----------------|-----------|
| "Add a new agent" | Run Goal Alignment Review + Overlap checklist |
| "Agents are doing duplicate work" | Diagnose with Monitoring section, fix with Overlap Avoidance |
| "Agent is stuck / not responding" | Check Monitoring alerts; activate kill switch if needed |
| "Instructions are contradicting each other" | Apply Conflict Blocking validator |
| "System is deadlocked" | Run deadlock detection, break with timeouts + kill switch |
