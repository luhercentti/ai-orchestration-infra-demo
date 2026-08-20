#!/usr/bin/env python3
"""Golden-path scaffold: generates a new agent node from a template so a new
team can add a specialist agent without hand-wiring boilerplate.

Usage:
    python platform/scaffold_agent.py cost_agent
"""
import sys
from pathlib import Path

TEMPLATE = '''"""{title} agent — TODO: describe what this agent does and what
part of shared state it reads/writes."""
from ..state import OrchestratorState


def {name}(state: OrchestratorState) -> dict:
    # TODO: implement. Read whatever fields you need from `state`, do the
    # work, and return only the keys you want merged back into shared state.
    history = state.get("history", []) + ["{name}: TODO implement"]
    return {{"history": history}}
'''

AGENTS_DIR = Path(__file__).resolve().parent.parent / "orchestrator" / "app" / "agents"


def main():
    if len(sys.argv) != 2:
        print("Usage: python platform/scaffold_agent.py <agent_name>")
        sys.exit(1)

    name = sys.argv[1]
    if not name.isidentifier():
        print(f"'{name}' is not a valid Python identifier for a module/function name")
        sys.exit(1)

    target = AGENTS_DIR / f"{name}.py"
    if target.exists():
        print(f"{target} already exists — pick a different name")
        sys.exit(1)

    title = name.replace("_", " ").title()
    target.write_text(TEMPLATE.format(name=name, title=title))
    print(f"Created {target}")
    print("Next steps:")
    print(f"  1. Implement the agent logic in {target}")
    print("  2. Register the node in orchestrator/app/graph.py (add_node + edge back to supervisor)")
    print("  3. Add a routing branch for it in orchestrator/app/agents/supervisor.py")
    print("  4. Add a unit test in tests/")


if __name__ == "__main__":
    main()
