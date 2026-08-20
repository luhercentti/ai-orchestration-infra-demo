.PHONY: dev down test new-agent lint

## Start the full local stack (Postgres, Redis, orchestrator) via Docker Compose
dev:
	docker compose up --build

## Stop and remove the local stack
down:
	docker compose down -v

## Run unit tests (no Docker required — uses the in-memory checkpointer)
## Creates .venv on first run; subsequent runs reuse it.
test:
	test -d .venv || python3.12 -m venv .venv
	.venv/bin/pip install -q -r orchestrator/requirements.txt -r tests/requirements.txt
	cd orchestrator && PYTHONPATH=. ../.venv/bin/python -m pytest ../tests -v

## Golden path: scaffold a new agent node (usage: make new-agent NAME=cost_agent)
new-agent:
	python platform/scaffold_agent.py $(NAME)
