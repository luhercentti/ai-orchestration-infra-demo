"""Optional LLM client. Falls back to deterministic heuristics when no API key
is configured, so the demo runs fully offline without degrading the graph shape."""
import os
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def get_llm():
    """Returns a LangChain chat model, or None if no provider is configured."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)


def classify(system_prompt: str, user_text: str) -> Optional[str]:
    """Single-shot text completion used by agents. Returns None if no LLM is
    configured, letting callers fall back to heuristics."""
    llm = get_llm()
    if llm is None:
        return None
    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
    )
    return response.content
