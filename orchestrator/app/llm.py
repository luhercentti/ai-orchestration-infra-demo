"""Optional LLM client. Falls back to deterministic heuristics when no API key
is configured, so the demo runs fully offline without degrading the graph shape."""
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm():
    """Returns a LangChain chat model, or None if no provider is configured.

    Set OPENAI_API_KEY to a real key to use OpenAI.
    Set OPENAI_API_KEY=ollama (and optionally OLLAMA_HOST) to use a local Ollama server.
    Leave unset to run in heuristic-only mode with no LLM calls.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    from langchain_openai import ChatOpenAI

    # Ollama speaks the OpenAI API format but on a different base URL.
    # Inside Docker, the host machine is reachable via host.docker.internal.
    if api_key.lower() == "ollama":
        base_url = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434/v1")
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "llama3.2"),
            base_url=base_url,
            api_key="ollama",
            temperature=0,
        )

    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)


def classify(system_prompt: str, user_text: str) -> Optional[str]:
    """Single-shot text completion. Returns None on any error so callers
    fall back to heuristics — LLM failures must never crash a graph run."""
    llm = get_llm()
    if llm is None:
        return None
    try:
        response = llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ]
        )
        return response.content
    except Exception as exc:
        logger.warning("LLM call failed, falling back to heuristics: %s", exc)
        return None
