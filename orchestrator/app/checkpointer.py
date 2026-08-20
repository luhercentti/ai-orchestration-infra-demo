"""Checkpointer factory: Postgres in real runs, in-memory for tests/CI.

Postgres is what makes runs durable/resumable across pod restarts; MemorySaver
is used by pytest so unit tests don't need a database.
"""
import os
from contextlib import contextmanager


@contextmanager
def get_checkpointer():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        from langgraph.checkpoint.memory import MemorySaver

        yield MemorySaver()
        return

    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()
        yield checkpointer
