# Jarvis Project - Claude Development Notes

## Critical: Server Runs in Docker

**The server runs in Docker, NOT locally.** Always check with:
```bash
ps aux | grep uvicorn
```

If you see `/app/.venv/bin/` in the path, it's Docker.

### To apply code changes:
```bash
cd /home/sven/Documents/jarvis/server
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Do NOT:
- Try to restart with `pkill` and `python -m jarvis_server.main` when Docker is running
- Assume local venv changes will take effect without rebuilding Docker

## Environment Configuration

- Server uses `JARVIS_` prefix for all env vars (e.g., `JARVIS_ANTHROPIC_API_KEY`)
- Docker-specific vars (POSTGRES_USER, etc.) don't need prefix
- `.env` file is in `.gitignore` - use `.env.example` as template
- Data directory for local dev: set `JARVIS_DATA_DIR`

## Project Structure

```
jarvis/
├── agent/          # Desktop capture agent (Python, runs locally)
├── server/         # FastAPI backend (runs in Docker)
│   ├── .env        # Local config (gitignored)
│   ├── docker-compose.yml
│   └── data/       # Local data directory
│       └── calendar/
│           └── credentials.json  # Google OAuth credentials
├── mcp/            # MCP server for Claude Code integration
└── .planning/      # GSD planning files
```

## Common Gotchas

1. **Settings class validation**: If adding new env vars, add them to `server/src/jarvis_server/config.py` Settings class or use `extra="ignore"`

2. **Google Calendar OAuth**: Requires browser access on same machine. Credentials go in `server/data/calendar/credentials.json` (mounted to `/data/calendar` in Docker)

3. **Port conflicts**: Docker binds to 8000. Kill with `fuser -k 8000/tcp` or `docker compose down`

4. **Import errors silent in FastAPI**: If routes are missing, check for import errors by running:
   ```bash
   python -c "from jarvis_server.main import app; print([r.path for r in app.routes])"
   ```

5. **Docker volume mounts for secrets**: Files like credentials.json must be volume-mounted in docker-compose.yml. Named volumes don't see local files - use bind mounts (`./data/calendar:/data/calendar`)

6. **Environment variables in Docker**: Pass through .env vars via `${VAR_NAME:-default}` in docker-compose.yml environment section

7. **OAuth in Docker**: Docker containers can't open browsers. Use `server/scripts/oauth_helper.py` locally to generate token.json, which Docker can then use via volume mount

8. **Hotfixing Docker without rebuild**: Copy files with `docker cp file.py container:/path/` then restart container. But model changes need migration rerun too

9. **Database migrations**: When changing models, create/update migration in `alembic/versions/`, copy to container, run `docker exec container alembic upgrade head`
