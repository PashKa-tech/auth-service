.PHONY: up down test-be build migrate

up:
	docker-compose up -d

down:
	docker-compose down

test-be:
	pytest backend/

build:
	docker-compose build

migrate:
	alembic upgrade head
