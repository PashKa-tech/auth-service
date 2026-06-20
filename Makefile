.PHONY: up down test-be build migrate lint-be scan

up:
	docker-compose up -d

down:
	docker-compose down

test-be:
	pytest backend/

build:
	docker-compose build

migrate:
	docker-compose exec backend alembic upgrade head

lint-be:
	docker-compose exec backend ruff check .

scan:
	docker-compose exec backend bandit -r .
