# 🏜️ DESERTAS Makefile
# Desert Emission Sensing & Energetic Rock-Tectonic Analysis System

.PHONY: help install dev test lint format clean build docs deploy dashboard api

SHELL := /bin/bash
VERSION := 1.0.0
DASHBOARD_URL := https://desertas.netlify.app
API_URL := https://desertas.netlify.app/api

help:
	@echo "🏜️ DESERTAS Makefile"
	@echo "======================"
	@echo "install     : Install DESERTAS"
	@echo "dev         : Install development dependencies"
	@echo "test        : Run tests"
	@echo "lint        : Run linters"
	@echo "format      : Format code"
	@echo "clean       : Clean build artifacts"
	@echo "build       : Build package"
	@echo "docs        : Build documentation"
	@echo "deploy-docs : Deploy to ReadTheDocs"
	@echo "dashboard   : Run dashboard locally"
	@echo "api         : Run API locally"
	@echo "demo        : Run demo"
	@echo "doctor      : Check system"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest tests/ -v --cov=desertas

test-hypothesis:
	pytest tests/hypothesis/ -v

lint:
	black --check desertas/ tests/
	ruff check desertas/ tests/
	mypy desertas/

format:
	black desertas/ tests/
	isort desertas/ tests/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf docs/_build/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build
	@echo "✅ Build complete. Dashboard: $(DASHBOARD_URL)"

docs:
	cd docs && make html
	@echo "📚 Documentation built. Open docs/_build/html/index.html"

deploy-docs:
	@echo "🚀 Deploying to ReadTheDocs..."
	@echo "👉 https://desertas.readthedocs.io"

dashboard:
	@echo "🚀 Starting dashboard..."
	@echo "👉 Local: http://localhost:8501"
	@echo "👉 Live: $(DASHBOARD_URL)"
	streamlit run dashboard/app.py --server.port 8501

api:
	@echo "🚀 Starting API..."
	@echo "👉 Local: http://localhost:8000"
	@echo "👉 Live: $(API_URL)"
	gunicorn --bind 0.0.0.0:8000 desertas.api.app:app

demo:
	python scripts/desertas_demo.py --station sahara-01

doctor:
	desertas doctor

docker-build:
	docker build -t desertas:$(VERSION) .

docker-run:
	docker run -p 8501:8501 -p 8000:8000 desertas:$(VERSION)

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

release: test build
	@echo "✅ Ready for release: $(VERSION)"
	@echo "👉 Dashboard: $(DASHBOARD_URL)"
	@echo "👉 API: $(API_URL)"
	@echo "👉 DOI: 10.14293/DESERTAS.2026.001"

.DEFAULT_GOAL := help
