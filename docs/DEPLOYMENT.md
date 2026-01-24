# Jarvis Server Deployment

This guide covers deploying the Jarvis server on a Hetzner VPS (or similar) with Docker Compose and Tailscale for secure access.

## Prerequisites

- Hetzner server (or similar VPS) with Docker installed
- Tailscale installed and configured on the server
- Tailscale installed on client machines that will access Jarvis

## Architecture

```
Client Machine (Linux/Mac)              Hetzner Server
+------------------+                    +------------------------+
| Jarvis Agent     |                    |  Docker Compose        |
| - Captures       | ---- Tailscale --> |  +------------------+  |
| - Uploads        |      (encrypted)   |  | jarvis-server    |  |
+------------------+                    |  | (port 8000)      |  |
                                        |  +--------+---------+  |
                                        |           |            |
                                        |  +--------v---------+  |
                                        |  | postgres         |  |
                                        |  | (port 5432)      |  |
                                        |  +------------------+  |
                                        |           |            |
                                        |  +--------v---------+  |
                                        |  | qdrant           |  |
                                        |  | (port 6333)      |  |
                                        |  +------------------+  |
                                        +------------------------+
```

All services bind to `127.0.0.1` only. Access is exclusively through Tailscale.

## Initial Setup

### 1. Install Docker on Server

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Start Docker service
sudo systemctl enable docker
sudo systemctl start docker
```

### 2. Install Tailscale on Server

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Start Tailscale and authenticate
sudo tailscale up

# Note the Tailscale IP (e.g., 100.x.y.z)
tailscale ip -4
```

### 3. Clone and Configure

```bash
# Clone the repository
git clone <repo-url> jarvis
cd jarvis/server

# Copy environment configuration
cp .env.example .env

# Edit .env with secure passwords
# IMPORTANT: Change POSTGRES_PASSWORD to a secure value
nano .env
```

### 4. Start Services

```bash
# Build and start all services
docker compose up -d

# View logs
docker compose logs -f
```

### 5. Run Database Migrations

```bash
# Run Alembic migrations
docker compose exec jarvis-server alembic upgrade head
```

### 6. Verify Deployment

```bash
# Check health endpoint (from server)
curl http://localhost:8000/health/

# Check readiness endpoint
curl http://localhost:8000/health/ready
```

## Security Configuration

### Tailscale-Only Access (SEC-03, SEC-04)

The server binds all ports to `127.0.0.1` only. This means:

- No direct internet access to services
- All access must go through Tailscale VPN
- Traffic is encrypted end-to-end

On client machines, configure the agent to use the Tailscale IP:

```bash
export JARVIS_SERVER_URL=http://100.x.y.z:8000
```

Replace `100.x.y.z` with your server's Tailscale IP.

### Firewall Rules (UFW)

```bash
# Allow Tailscale interface
sudo ufw allow in on tailscale0

# Block direct access to server ports (already bound to localhost, but extra safety)
sudo ufw deny 8000
sudo ufw deny 5432
sudo ufw deny 6333

# Enable firewall
sudo ufw enable
```

### Firewall Rules (iptables)

```bash
# Accept Tailscale traffic
sudo iptables -A INPUT -i tailscale0 -j ACCEPT

# Drop direct access attempts
sudo iptables -A INPUT -p tcp --dport 8000 -j DROP
sudo iptables -A INPUT -p tcp --dport 5432 -j DROP
sudo iptables -A INPUT -p tcp --dport 6333 -j DROP
```

## Managing Services

### Start/Stop/Restart

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# Restart a specific service
docker compose restart jarvis-server

# Rebuild after code changes
docker compose up -d --build
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f jarvis-server
docker compose logs -f postgres
docker compose logs -f qdrant
```

### Check Status

```bash
# Container status
docker compose ps

# Resource usage
docker stats
```

## Monitoring

### Health Endpoints

| Endpoint        | Purpose                              | Success |
|-----------------|--------------------------------------|---------|
| `/health/`      | Basic status (for dashboards)        | 200     |
| `/health/ready` | Full readiness (for load balancers)  | 200     |

The `/health/ready` endpoint returns 503 if any component is unhealthy.

### Container Health

Docker Compose includes healthchecks for all services:

```bash
# View health status
docker inspect jarvis-server --format='{{.State.Health.Status}}'
docker inspect jarvis-postgres --format='{{.State.Health.Status}}'
```

## Backup

### Important Data Volumes

| Volume               | Contains                        | Priority |
|----------------------|--------------------------------|----------|
| `jarvis-postgres-data` | Database (captures, metadata)  | Critical |
| `jarvis-qdrant-data`   | Vector embeddings              | High     |
| `jarvis-captures`      | Screenshot files               | High     |

### Backup Commands

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U jarvis jarvis > backup.sql

# Backup volumes (stop services first for consistency)
docker compose down
sudo tar -czvf jarvis-backup.tar.gz \
    /var/lib/docker/volumes/jarvis-postgres-data \
    /var/lib/docker/volumes/jarvis-qdrant-data \
    /var/lib/docker/volumes/jarvis-captures
docker compose up -d
```

### Restore Commands

```bash
# Restore PostgreSQL
cat backup.sql | docker compose exec -T postgres psql -U jarvis jarvis

# Restore volumes
docker compose down
sudo tar -xzvf jarvis-backup.tar.gz -C /
docker compose up -d
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose down
docker compose up -d --build

# Run any new migrations
docker compose exec jarvis-server alembic upgrade head
```

## Troubleshooting

### Services Won't Start

```bash
# Check for port conflicts
sudo lsof -i :5432
sudo lsof -i :6333
sudo lsof -i :8000

# Check Docker logs
docker compose logs
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
docker compose exec postgres psql -U jarvis -c "SELECT 1"

# Check environment variables
docker compose config
```

### Server Not Accessible via Tailscale

```bash
# Verify Tailscale is running
tailscale status

# Check server is listening
curl http://localhost:8000/health/

# From client, check Tailscale connectivity
ping 100.x.y.z
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean Docker resources
docker system prune -a

# Check volume sizes
docker system df -v
```

## Environment Variables

| Variable              | Description                     | Default                |
|-----------------------|---------------------------------|------------------------|
| `POSTGRES_USER`       | PostgreSQL username             | `jarvis`               |
| `POSTGRES_PASSWORD`   | PostgreSQL password             | `changeme`             |
| `POSTGRES_DB`         | PostgreSQL database name        | `jarvis`               |
| `JARVIS_LOG_LEVEL`    | Logging level                   | `INFO`                 |
| `JARVIS_STORAGE_PATH` | Path for capture files          | `/data/captures`       |
| `JARVIS_QDRANT_HOST`  | Qdrant hostname                 | `qdrant`               |
| `JARVIS_QDRANT_PORT`  | Qdrant port                     | `6333`                 |

---

*Last updated: 2026-01-24*
