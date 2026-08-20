"""FastAPI entrypoint for the infra request copilot.

Endpoints:
  POST /requests               start a new orchestration run
  GET  /requests/{thread_id}   inspect current state / pending approval
  POST /requests/{thread_id}/approve   resume a paused run with a decision
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from .checkpointer import get_checkpointer
from .graph import build_graph
from .tracing import graph_config_with_tracing

_checkpointer_cm = None
_app_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _checkpointer_cm, _app_graph
    _checkpointer_cm = get_checkpointer()
    checkpointer = _checkpointer_cm.__enter__()
    _app_graph = build_graph(checkpointer)
    yield
    _checkpointer_cm.__exit__(None, None, None)


app = FastAPI(title="Infra Request Copilot", lifespan=lifespan)


class InfraRequestIn(BaseModel):
    raw_text: str
    requester: str


class ApprovalIn(BaseModel):
    approval: str  # "approved" | "rejected"
    approver: str


def _serialize(snapshot) -> dict:
    pending_interrupts = []
    for task in snapshot.tasks:
        pending_interrupts.extend({"value": i.value} for i in task.interrupts)
    return {"values": snapshot.values, "next_nodes": snapshot.next, "interrupts": pending_interrupts}


@app.post("/requests")
def create_request(payload: InfraRequestIn):
    thread_id = str(uuid.uuid4())
    config = graph_config_with_tracing({"configurable": {"thread_id": thread_id}})
    initial_state = {"request": payload.model_dump(), "history": []}
    _app_graph.invoke(initial_state, config)
    return {"thread_id": thread_id, **_serialize(_app_graph.get_state(config))}


@app.get("/requests/{thread_id}")
def get_request(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = _app_graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="unknown thread_id")
    return _serialize(snapshot)


@app.post("/requests/{thread_id}/approve")
def approve_request(thread_id: str, payload: ApprovalIn):
    config = graph_config_with_tracing({"configurable": {"thread_id": thread_id}})
    _app_graph.invoke(Command(resume=payload.model_dump()), config)
    return _serialize(_app_graph.get_state(config))


@app.get("/health")
def health():
    return {"status": "ok"}
