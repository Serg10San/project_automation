"""
context_window.py — Context window token counter and compression manager.

Tracks token usage across a conversation, warns when approaching the model's
limit, and compresses history so the session can continue indefinitely.

Usage (import):
    from context_window import ContextWindowManager
    mgr = ContextWindowManager(model="gpt-4o")
    messages = mgr.add_user("Hello, world!")
    if mgr.should_compress(messages):
        messages = mgr.compress(messages, client)

Usage (background monitor):
    with ContextWindowManager(model="gpt-4o", monitor=True) as mgr:
        ...  # mgr.report() is logged every 60 s in a daemon thread

Usage (CLI demo):
    python context_window.py
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import tiktoken
except ImportError:
    raise SystemExit("tiktoken is required: pip install tiktoken")

logger = logging.getLogger(__name__)

# ── Model limits ──────────────────────────────────────────────────────────────

MODEL_LIMITS: dict[str, int] = {
    "gpt-4o":               128_000,
    "gpt-4o-mini":          128_000,
    "gpt-4-turbo":          128_000,
    "gpt-4":                  8_192,
    "gpt-3.5-turbo":         16_385,
    "claude-3-5-sonnet":    200_000,
    "claude-3-opus":        200_000,
    "claude-sonnet-4":      200_000,
}

DEFAULT_COMPRESSION_THRESHOLD = 0.75   # compress at 75 % full
DEFAULT_MODEL = "gpt-4o"


# ── Token counting ────────────────────────────────────────────────────────────

def count_tokens(messages: list[dict], model: str = DEFAULT_MODEL) -> int:
    """Return the total number of tokens consumed by a message list.

    Includes per-message overhead (role prefix + separators) and the
    two-token reply-priming cost that the API adds automatically.
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")

    total = 0
    for msg in messages:
        total += 4                              # role + structural tokens
        content = msg.get("content") or ""
        if isinstance(content, list):           # vision / multi-modal content
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        total += len(enc.encode(content))
    total += 2                                  # reply priming
    return total


# ── Report ────────────────────────────────────────────────────────────────────

@dataclass
class ContextWindowReport:
    model: str
    used_tokens: int
    limit_tokens: int
    compression_threshold: int
    pct_used: float
    needs_compression: bool
    messages: int

    def __str__(self) -> str:
        bar_width = 30
        filled = int(self.pct_used / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        flag = "  ⚠️  COMPRESS NOW" if self.needs_compression else ""
        return (
            f"[{self.model}] [{bar}] "
            f"{self.used_tokens:,} / {self.limit_tokens:,} tokens "
            f"({self.pct_used:.1f}%) — {self.messages} messages{flag}"
        )

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "used_tokens": self.used_tokens,
            "limit_tokens": self.limit_tokens,
            "compression_threshold": self.compression_threshold,
            "pct_used": round(self.pct_used, 2),
            "needs_compression": self.needs_compression,
            "messages": self.messages,
        }


# ── Manager ───────────────────────────────────────────────────────────────────

class ContextWindowManager:
    """Tracks token usage, triggers compression, and optionally monitors in the background.

    Args:
        model: Model name — used to look up the context limit and tokeniser.
        threshold: Fraction of the context limit at which compression fires (default 0.75).
        monitor: If True, start a background daemon thread that logs the token
                 report every ``monitor_interval`` seconds.
        monitor_interval: Seconds between background log entries (default 60).
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        threshold: float = DEFAULT_COMPRESSION_THRESHOLD,
        monitor: bool = False,
        monitor_interval: int = 60,
    ) -> None:
        self.model = model
        self.limit = MODEL_LIMITS.get(model, 128_000)
        self.threshold = threshold
        self.compression_threshold = int(self.limit * threshold)
        self._messages: list[dict] = []
        self._compressions = 0
        self._monitor_interval = monitor_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        if monitor:
            self._start_monitor()

    # ── Context manager support ───────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop_monitor()

    # ── Message helpers ───────────────────────────────────────────────────────

    def add_user(self, content: str) -> list[dict]:
        self._messages.append({"role": "user", "content": content})
        return self._messages

    def add_assistant(self, content: str) -> list[dict]:
        self._messages.append({"role": "assistant", "content": content})
        return self._messages

    # ── Core API ──────────────────────────────────────────────────────────────

    def report(self, messages: Optional[list[dict]] = None) -> ContextWindowReport:
        """Return a ContextWindowReport for the given message list."""
        msgs = messages if messages is not None else self._messages
        used = count_tokens(msgs, self.model)
        pct = used / self.limit * 100
        return ContextWindowReport(
            model=self.model,
            used_tokens=used,
            limit_tokens=self.limit,
            compression_threshold=self.compression_threshold,
            pct_used=pct,
            needs_compression=used >= self.compression_threshold,
            messages=len(msgs),
        )

    def should_compress(self, messages: Optional[list[dict]] = None) -> bool:
        """Return True when the token count has reached the compression threshold."""
        msgs = messages if messages is not None else self._messages
        return count_tokens(msgs, self.model) >= self.compression_threshold

    def compress(self, messages: list[dict], client=None) -> list[dict]:
        """Summarise the conversation history and return a shorter message list.

        The system prompt is always preserved verbatim. All other messages are
        replaced with a single summary assistant message.

        Args:
            messages: Current message list.
            client: An OpenAI-compatible client. If None, uses a simple
                    heuristic summary (useful for testing without an API key).

        Returns:
            A new, shorter message list.
        """
        system = [m for m in messages if m.get("role") == "system"]
        history = [m for m in messages if m.get("role") != "system"]

        before = count_tokens(messages, self.model)

        if client is not None:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a conversation summariser. Produce a concise summary "
                            "of the conversation below, preserving all key facts, decisions, "
                            "code snippets, variable values, and open questions. "
                            "Write in third person. Be thorough — this replaces the full history."
                        ),
                    },
                    {"role": "user", "content": json.dumps(history, ensure_ascii=False)},
                ],
            )
            summary = resp.choices[0].message.content
        else:
            # Fallback: last 6 messages verbatim (no API needed — useful for demos)
            kept = history[-6:]
            summary = (
                "[Summary — no client provided; last 6 messages kept verbatim]\n"
                + json.dumps(kept, indent=2, ensure_ascii=False)
            )

        compressed = system + [{"role": "assistant", "content": f"[SUMMARY]\n{summary}"}]
        after = count_tokens(compressed, self.model)

        self._compressions += 1
        logger.info(
            "Compression #%d: %s → %s tokens (saved %s)",
            self._compressions,
            f"{before:,}",
            f"{after:,}",
            f"{before - after:,}",
        )
        self._messages = compressed
        return compressed

    def auto_compress(self, messages: list[dict], client=None) -> list[dict]:
        """Compress only if should_compress() returns True. Idempotent otherwise."""
        if self.should_compress(messages):
            r = self.report(messages)
            logger.warning("Context at %.1f%% — compressing...", r.pct_used)
            return self.compress(messages, client)
        return messages

    # ── Background monitor ────────────────────────────────────────────────────

    def _start_monitor(self) -> None:
        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="ctx-window-monitor"
        )
        self._thread.start()
        logger.info("Background context-window monitor started (interval=%ds)", self._monitor_interval)

    def _monitor_loop(self) -> None:
        while not self._stop_event.wait(self._monitor_interval):
            r = self.report()
            if r.needs_compression:
                logger.warning(str(r))
            else:
                logger.info(str(r))

    def stop_monitor(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)


# ── CLI demo ──────────────────────────────────────────────────────────────────

def _demo() -> None:
    """Interactive demo — no API key required."""
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    print(f"\n  Context Window Manager — demo ({model})")
    print(f"  Limit: {MODEL_LIMITS.get(model, 128_000):,} tokens")
    print(f"  Compression threshold: 75 %")
    print(f"  Type messages and watch the token counter. Type 'quit' to exit.\n")

    mgr = ContextWindowManager(model=model)
    messages: list[dict] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.lower() in {"quit", "exit", "q"}:
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # Simulate an assistant reply for the demo
        reply = f"[demo reply to: {user_input[:40]}]"
        messages.append({"role": "assistant", "content": reply})

        # Show report after every turn
        r = mgr.report(messages)
        print(f"\n{r}\n")

        # Auto-compress (no client — uses fallback summary)
        if r.needs_compression:
            print("  → Compressing history...")
            messages = mgr.compress(messages)
            r2 = mgr.report(messages)
            print(f"  → After compression: {r2}\n")

    print(f"\nSession ended. Total compressions: {mgr._compressions}")


if __name__ == "__main__":
    _demo()
