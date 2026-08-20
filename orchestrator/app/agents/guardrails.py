"""Guardrails node — runs before spec_agent on every request.

Blocks two classes of threats:
1. Destructive intent — requests asking to delete, destroy, or terminate resources
2. Prompt injection — attempts to override agent instructions via crafted input

Returns immediately with status "blocked" if either check fails, so the graph
never reaches spec_agent or any downstream agent.
"""
import re

from ..state import OrchestratorState

# Phrases that indicate destructive intent — case-insensitive, word-boundary matched
_DESTRUCTIVE_PATTERNS = [
    r"\bdelete\b", r"\bdestroy\b", r"\bterminate\b", r"\bremove\b",
    r"\bdrop\b", r"\bwipe\b", r"\bnuke\b", r"\bpurge\b",
    r"\bdecommission\b", r"\bshutdown\b", r"\bkill\b",
    r"\btruncate\b", r"\bformat\b", r"\bdetach\b",
]

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior|above|all)\s+instructions?",
    r"disregard\s+(previous|prior|above|all)",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+you\s+are|a\s+)",
    r"new\s+instructions?:",
    r"system\s*prompt\s*:",
    r"<\s*system\s*>",
    r"\[system\]",
    r"forget\s+(everything|all)\s+(you|your)",
]

_DESTRUCTIVE_RE = re.compile("|".join(_DESTRUCTIVE_PATTERNS), re.IGNORECASE)
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def guardrails(state: OrchestratorState) -> dict:
    text = state["request"].get("raw_text", "")

    if _INJECTION_RE.search(text):
        history = state.get("history", []) + ["guardrails: blocked (prompt injection attempt)"]
        return {"status": "blocked", "block_reason": "prompt injection detected", "history": history}

    if _DESTRUCTIVE_RE.search(text):
        history = state.get("history", []) + ["guardrails: blocked (destructive intent)"]
        return {
            "status": "blocked",
            "block_reason": (
                "destructive actions are not supported — this system provisions resources only. "
                "To decommission infrastructure open a change request with the platform team."
            ),
            "history": history,
        }

    history = state.get("history", []) + ["guardrails: passed"]
    return {"history": history}
