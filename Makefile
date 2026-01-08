.PHONY: help setup qdrant-up qdrant-down ingest-chatgpt ingest-anthropic chunks embed serve clean

DB ?= memory.sqlite
CHATGPT_EXPORT ?=
ANTHROPIC_EXPORT ?=
GROK_EXPORT ?=

help:
	@echo "Unified Memory MCP - Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          Install Python dependencies"
	@echo "  make qdrant-up      Start Qdrant container"
	@echo "  make qdrant-down    Stop Qdrant container"
	@echo ""
	@echo "Ingestion:"
	@echo "  make ingest-chatgpt CHATGPT_EXPORT=/path/to/conversations.json"
	@echo "  make ingest-anthropic ANTHROPIC_EXPORT=/path/to/conversations.json"
	@echo "  make ingest-grok GROK_EXPORT=/path/to/export.json"
	@echo ""
	@echo "Indexing:"
	@echo "  make chunks         Build chunks from messages"
	@echo "  make embed          Embed chunks to Qdrant"
	@echo "  make index          Build chunks + embed (both)"
	@echo ""
	@echo "Server:"
	@echo "  make serve          Start MCP server (SSE transport)"
	@echo "  make serve-stdio    Start MCP server (stdio transport)"
	@echo ""
	@echo "Options:"
	@echo "  DB=memory.sqlite    SQLite database path"

setup:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -r vendor/chat-export-structurer/requirements.txt
	@echo "Setup complete. Run: source .venv/bin/activate"

qdrant-up:
	docker compose up -d

qdrant-down:
	docker compose down

ingest-chatgpt:
	@if [ -z "$(CHATGPT_EXPORT)" ]; then echo "Error: CHATGPT_EXPORT not set"; exit 1; fi
	python vendor/chat-export-structurer/src/ingest.py \
		--in "$(CHATGPT_EXPORT)" \
		--db "$(DB)" \
		--format chatgpt

ingest-anthropic:
	@if [ -z "$(ANTHROPIC_EXPORT)" ]; then echo "Error: ANTHROPIC_EXPORT not set"; exit 1; fi
	python vendor/chat-export-structurer/src/ingest.py \
		--in "$(ANTHROPIC_EXPORT)" \
		--db "$(DB)" \
		--format anthropic

ingest-grok:
	@if [ -z "$(GROK_EXPORT)" ]; then echo "Error: GROK_EXPORT not set"; exit 1; fi
	python vendor/chat-export-structurer/src/ingest.py \
		--in "$(GROK_EXPORT)" \
		--db "$(DB)" \
		--format grok

chunks:
	python indexer.py build-chunks --db "$(DB)"

embed:
	python indexer.py embed --db "$(DB)"

index: chunks embed

serve:
	python server.py --db "$(DB)" --transport sse

serve-stdio:
	python server.py --db "$(DB)" --transport stdio

clean:
	rm -f "$(DB)"
	docker compose down -v
