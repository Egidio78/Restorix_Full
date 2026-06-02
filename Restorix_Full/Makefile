.PHONY: dev up down logs migrate test shell

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose exec api alembic upgrade head

test:
	docker compose exec api pytest tests/ -v

shell:
	docker compose exec api bash
