# Makefile for engineericly Docker management

.PHONY: help build up deploy down restart logs shell clean migrate collectstatic createsuperuser install test test-local

help:
	@echo "Available commands:"
	@echo "  deploy          - Pull the latest code, rebuild the image and restart (use on the server)"
	@echo "  build           - Build the image locally"
	@echo "  up              - Start the containers"
	@echo "  down            - Stop and remove containers"
	@echo "  restart         - Restart services"
	@echo "  logs            - Follow logs"
	@echo "  shell           - Open a shell in the web container"
	@echo "  migrate         - Run Django migrations"
	@echo "  collectstatic   - Collect static files"
	@echo "  createsuperuser - Create a Django admin user"
	@echo "  test            - Run tests inside the container"
	@echo "  test-local      - Run tests in the local .venv"

build:
	docker compose build

up:
	docker compose up -d

deploy:
	git pull --ff-only
	docker compose up -d --build --remove-orphans
	docker image prune -f

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

shell:
	docker compose exec web bash

migrate:
	docker compose exec web python manage.py migrate

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

createsuperuser:
	docker compose exec web python manage.py createsuperuser

# Stops containers; the data folder on disk is left alone.
clean:
	docker compose down --remove-orphans
	docker image prune -f

install:
	pip install -r requirements.txt

test:
	docker compose exec web python manage.py test

test-local:
	.venv/bin/python manage.py test
