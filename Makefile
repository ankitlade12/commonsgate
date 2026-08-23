.PHONY: install test proof api agent web-install web web-check check

install:
	uv sync --extra dev

test:
	uv run pytest

proof:
	uv run commonsgate

api:
	uv run commonsgate-api

agent:
	uv run adk api_server --host 0.0.0.0 --port 8081 --a2a commonsgate_agent

web-install:
	cd apps/web && npm install

web:
	cd apps/web && npm run dev

web-check:
	cd apps/web && npm run typecheck && npm run build

check:
	uv run pytest
	uv run ruff check .
	uv run mypy src commonsgate_agent
	uv run python -m compileall -q src commonsgate_agent tests
	cd apps/web && npm run typecheck && npm run build
