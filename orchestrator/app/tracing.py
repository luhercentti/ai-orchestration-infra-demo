"""Optional Langfuse tracing. No-op if LANGFUSE_* env vars aren't set, so the
demo runs without a tracing backend when you just want the graph itself."""
import os
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def get_langfuse_handler() -> Optional[object]:
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None

    from langfuse.callback import CallbackHandler

    return CallbackHandler(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )


def graph_config_with_tracing(config: dict) -> dict:
    """Attaches the Langfuse callback to a LangGraph invoke config, if configured."""
    handler = get_langfuse_handler()
    if handler is None:
        return config
    callbacks = config.get("callbacks", [])
    return {**config, "callbacks": [*callbacks, handler]}
