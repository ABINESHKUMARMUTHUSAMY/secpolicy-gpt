.PHONY: install run dev docker-build docker-up clean

venv:
	python3.12 -m venv .venv && source .venv/bin/activate

install:
	pip install -r requirements.txt

run:
	uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

dev:
	ANTHROPIC_API_KEY=$(shell cat .env | grep ANTHROPIC_API_KEY | cut -d= -f2) \
	uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-logs:
	docker compose logs -f

clean:
	rm -rf chroma_db __pycache__ backend/__pycache__ \
	       backend/rag/__pycache__ backend/ingestion/__pycache__ \
	       backend/mapping/__pycache__ backend/models/__pycache__
