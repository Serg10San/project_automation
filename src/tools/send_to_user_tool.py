"""
send_to_user_tool.py — Fable 5 / Mythos 5 verbatim message delivery tool.

For long asynchronous agents, this tool lets the agent surface a message to the
user exactly as written without ending its turn. Tool inputs are never summarized
by the Anthropic API, so content arrives intact.

Usage:
    Register this tool in your agent's tool list (see TOOL_SCHEMA below).
    Add the elicitation instruction to your system prompt (see SYSTEM_PROMPT_INSTRUCTION).
    Implement handle_send_to_user() to render the message in your UI.

See .github/skills/fable5-agentic-patterns.md for full context.
"""

import json
from typing import Any

# ── Tool schema — pass this in your tools list to the Anthropic API ───────────

TOOL_SCHEMA: dict[str, Any] = {
    "name": "send_to_user",
    "description": (
        "Display a message directly to the user. Use for progress updates, "
        "partial results, or content the user must see exactly as written "
        "before the task finishes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The content to display to the user.",
            }
        },
        "required": ["message"],
    },
}

# ── System prompt instruction — include in your agent system prompt ────────────

SYSTEM_PROMPT_INSTRUCTION = """
Between tool calls, when you have content the user must read verbatim (a partial
deliverable, a direct answer to their question, a progress update with specific
numbers), call send_to_user with that content. Use send_to_user only for
user-facing content — not for narration, reasoning, or routine progress notes.
"""

# ── Handler — implement this to render the message in your UI ─────────────────


def handle_send_to_user(tool_input: dict[str, Any]) -> str:
    """
    Called when the agent invokes the send_to_user tool.

    Renders message to the user and returns a simple acknowledgement
    as the tool result. The agent continues its turn after this call.

    Replace the print() call with your UI rendering logic
    (e.g., WebSocket push, Slack message, queue event).
    """
    message = tool_input.get("message", "")

    # ── Replace with your UI delivery mechanism ───────────────────────────────
    print(f"\n[AGENT MESSAGE]\n{message}\n")
    # ─────────────────────────────────────────────────────────────────────────

    return json.dumps({"status": "delivered", "length": len(message)})


# ── Tool dispatcher — wire into your agent's tool call loop ──────────────────


def dispatch_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """
    Example dispatcher. Extend with your other tools.

    In your agent loop:
        for tool_call in response.content:
            if tool_call.type == "tool_use":
                result = dispatch_tool(tool_call.name, tool_call.input)
    """
    if tool_name == "send_to_user":
        return handle_send_to_user(tool_input)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
