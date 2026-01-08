# 🤖 JARVIS - AI Chief of Staff Memory System

**Unified Memory & Knowledge Graph for Executive AI Assistance**

JARVIS is a complete memory and intelligence system that powers your AI Chief of Staff. It combines SQLite-based knowledge graphs, semantic search, and proactive intelligence to provide context-aware executive assistance.

## 🚀 What is JARVIS?

JARVIS transforms conversations and observations into a persistent knowledge graph that:
- **Remembers everything** - Stores entities (people, projects, concepts) and their relationships
- **Learns continuously** - Extracts insights from conversations and observations
- **Suggests proactively** - Surfaces relevant context before you ask
- **Integrates seamlessly** - RESTful API for any frontend or service

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│  Frontend Dashboard                         │
│  (Vercel / React)                           │
└─────────────────┬───────────────────────────┘
                  │ HTTP/WebSocket
                  ▼
┌─────────────────────────────────────────────┐
│  Exec Backend                               │
│  (Node.js/TypeScript - Port 3001)          │
│  - OKR Tracking                             │
│  - Calendar/Gmail Integration               │
│  - Memory Service Client                    │
└─────────────────┬───────────────────────────┘
                  │ REST API
                  ▼
┌─────────────────────────────────────────────┐
│  JARVIS Memory API (This Repo)              │
│  (Python/FastAPI - Port 8765)               │
│  - Unified Memory Database                  │
│  - Intelligence Engine                      │
│  - Proactive Suggestions                    │
└─────────────────┬───────────────────────────┘
                  │
                  ├──► SQLite (Knowledge Graph)
                  └──► Qdrant (Vector Search)
```

## ✨ Features

### Core Memory System
- **Knowledge Graph** - Entities, observations, relations, and semantic beliefs
- **Hybrid Search** - Combines lexical (FTS5) and semantic (Qdrant) search
- **Entity Extraction** - Automatic extraction of people, projects, concepts
- **Belief Tracking** - Captures preferences, facts, and decisions over time

### Intelligence Layer
- **Proactive Suggestions** - Surfaces relevant context before you need it
- **Executive Briefs** - Summarizes recent activity and decisions
- **Contradiction Detection** - Alerts when beliefs change
- **Pattern Recognition** - Identifies temporal patterns and trends

### API Endpoints
- `POST /memory/observation` - Store new observations
- `POST /memory/entity` - Create entities
- `POST /api/search` - Hybrid search
- `GET /api/stats` - System statistics
- `POST /api/suggestions` - Proactive suggestions
- `GET /health` - Health check

## 🚦 Quick Start

### 1. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start Memory API
```bash
API_PORT=8765 python api_bridge.py
```

### 3. Test the System
```bash
# Health check
curl http://localhost:8765/health

# Add a memory
curl -X POST http://localhost:8765/memory/observation \
  -H "Content-Type: application/json" \
  -d '{
    "entity_name": "Sven",
    "content": "Working on JARVIS integration",
    "source": "manual"
  }'

# Search memories
curl -X POST http://localhost:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "JARVIS", "limit": 5}'
```

## 📊 System Components

### Core Files
- `api_bridge.py` - FastAPI server exposing memory capabilities
- `unified_memory.py` - Knowledge graph database layer
- `intelligence.py` - AI-powered entity extraction and suggestions
- `server.py` - MCP server for Claude integration
- `webapp.py` - Web UI for memory exploration

### Database Schema
- **entities** - People, projects, technologies, concepts, organizations
- **observations** - Facts and insights about entities
- **relations** - Relationships between entities
- **semantic_beliefs** - Preferences, decisions, and facts
- **chunks** - Conversation segments for search

## 🔧 Configuration

### Environment Variables
```bash
# API Port
API_PORT=8765

# Database Path
DB_PATH=./memory.sqlite

# Qdrant Vector Database
QDRANT_URL=http://localhost:6333

# OpenAI for Intelligence Features
OPENAI_API_KEY=your_key_here
```

### Starting Qdrant (Optional - for semantic search)
```bash
docker-compose up -d qdrant
```

## 📚 Documentation

- **Deployment Guide**: `JARVIS_DEPLOYMENT_COMPLETE.md`
- **Complete Guide**: `JARVIS_COMPLETE_GUIDE.md`
- **Test Results**: `JARVIS_TEST_RESULTS.md`
- **API Docs**: http://localhost:8765/docs (when running)

## 🎯 Use Cases

### Daily Executive Logging
```python
# Morning sync
POST /memory/observation
{
  "entity_name": "Sven",
  "content": "Starting day with Atlas Intelligence GTM priorities",
  "source": "morning_sync"
}
```

### Project Tracking
```python
# Project update
POST /memory/observation
{
  "entity_name": "Atlas Intelligence",
  "content": "Day 3: 45 inbound leads, 7 discovery calls booked",
  "source": "project_update"
}
```

### Decision Logging
```python
# Strategic decision
POST /memory/observation
{
  "entity_name": "Sven",
  "content": "DECISION: Lead with 65K Readiness Sprint instead of 290K Foundation",
  "source": "strategic_decision"
}
```

## 🔌 Integration

### With Exec Backend
The backend connects via `MEMORY_MCP_URL`:
```typescript
const memoryService = new MemoryService('http://localhost:8765');
const results = await memoryService.search(query);
```

### With Claude Desktop (MCP)
Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "unified-memory": {
      "command": "python",
      "args": ["/path/to/memory-rag/server.py"],
      "env": {
        "DB_PATH": "/path/to/memory.sqlite"
      }
    }
  }
}
```

## 🛠️ Development

### Running Tests
```bash
# Run test script
bash test_api.sh

# Manual testing
python -m pytest tests/
```

### Adding New Features
1. Extend `unified_memory.py` for new database capabilities
2. Add endpoints in `api_bridge.py`
3. Update `intelligence.py` for AI-powered features
4. Document in this README

## 📦 Related Repositories

- **Frontend**: [Executive Assistant Dashboard](https://frontend-xi-ashen.vercel.app)
- **Backend**: [Exec Backend](https://github.com/Arnarsson/exec)
- **CoS System**: Chief of Staff orchestration system

## 🤝 Contributing

This is a personal AI Chief of Staff system, but feel free to fork and adapt for your own use!

## 📜 License

MIT License - See LICENSE file for details

---

**Status:** 🟢 **OPERATIONAL**  
**Version:** 1.0.0  
**Last Updated:** January 8, 2026

🤖✨ **Your AI Chief of Staff's Memory Core** ✨🤖
