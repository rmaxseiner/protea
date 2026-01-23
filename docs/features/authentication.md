# Authentication Guide

Protea Inventory supports multi-user authentication with web UI sessions and API key authentication for MCP clients.

## Table of Contents

- [Quick Start](#quick-start)
- [First-Time Setup](#first-time-setup)
- [Environment Variables](#environment-variables)
- [Web UI Authentication](#web-ui-authentication)
- [API Key Management](#api-key-management)
- [MCP Client Configuration](#mcp-client-configuration)
- [Docker Deployment](#docker-deployment)
- [Development Mode](#development-mode)
- [Security Considerations](#security-considerations)

---

## Quick Start

1. Start Protea for the first time
2. Check the logs for the generated admin password
3. Log in to the web UI at `http://localhost:8080`
4. Change the admin password when prompted
5. Generate an API key in Settings for MCP clients

---

## First-Time Setup

When Protea starts with an empty database, it automatically creates an admin user:

```
==================================================
FIRST-RUN: Admin user created
Username: admin
Password: Xk9#mP2$vL7nQ4wR
==================================================
```

**Important:** Copy this password immediately - it's only shown once!

### Setting a Known Admin Password

To set a specific admin password (useful for automation), set the environment variable before first startup:

```bash
export PROTEA_ADMIN_PASSWORD="YourSecurePassword1!"
protea-web
```

### Password Requirements

All passwords must meet these complexity requirements:
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 number
- At least 1 special character: `!@#$%^&*_+-=`

---

## Environment Variables

All authentication settings use the `PROTEA_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROTEA_ADMIN_PASSWORD` | (random) | Initial admin password on first run |
| `PROTEA_API_KEY` | (none) | Legacy single API key for all clients |
| `PROTEA_SESSION_HOURS` | `24` | Web session duration in hours |
| `PROTEA_AUTH_REQUIRED` | `true` | Set to `false` to disable authentication |

---

## Web UI Authentication

### Login

Navigate to `http://localhost:8080`. If not authenticated, you'll be redirected to the login page.

### Creating Additional Users

1. Log in as admin
2. New users can sign up via `/auth/signup`
3. Or share the signup link: `http://localhost:8080/auth/signup`

### Changing Password

1. Go to Settings (gear icon in sidebar)
2. Click "Change Password"
3. Enter current password and new password

---

## API Key Management

API keys allow MCP clients (like Claude Desktop) to authenticate with Protea.

### Creating an API Key

1. Log in to the web UI
2. Go to **Settings**
3. Enter a name for the key (e.g., "Claude Desktop")
4. Click **Create Key**
5. **Copy the key immediately** - it's only shown once!

API keys have the format: `prot_` followed by a random string.

Example: `prot_Xk9mP2vL7nQ4wRbT8yF3hJ6kM1pN5sD9`

### Revoking API Keys

1. Go to Settings
2. Find the key in the list
3. Click **Revoke** (keeps the key for audit) or **Delete** (permanent)

---

## MCP Client Configuration

### Claude Desktop - SSE Transport (Recommended)

Add to your Claude Desktop MCP configuration (`~/.config/claude/claude_desktop_config.json` on Linux or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "protea": {
      "transport": {
        "type": "sse",
        "url": "http://localhost:8081/sse",
        "headers": {
          "Authorization": "Bearer prot_YOUR_API_KEY_HERE"
        }
      }
    }
  }
}
```

### Claude Desktop - Stdio Transport

For stdio transport, pass the API key as an environment variable:

```json
{
  "mcpServers": {
    "protea": {
      "command": "protea",
      "env": {
        "PROTEA_API_KEY": "prot_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Claude Desktop - Stdio with UV (Development)

If running from source with uv:

```json
{
  "mcpServers": {
    "protea": {
      "command": "uv",
      "args": ["run", "protea"],
      "cwd": "/path/to/protea",
      "env": {
        "PROTEA_API_KEY": "prot_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Remote Server Configuration

For a remote Protea server:

```json
{
  "mcpServers": {
    "protea": {
      "transport": {
        "type": "sse",
        "url": "https://protea.example.com/sse",
        "headers": {
          "Authorization": "Bearer prot_YOUR_API_KEY_HERE"
        }
      }
    }
  }
}
```

---

## Docker Deployment

### Basic Docker Run

```bash
# First run - check logs for admin password
docker run -d \
  --name protea \
  -p 8080:8080 \
  -p 8081:8081 \
  -v protea-data:/app/data \
  protea:latest

# Check logs for admin password
docker logs protea | grep -A3 "FIRST-RUN"
```

### Docker Run with Known Admin Password

```bash
docker run -d \
  --name protea \
  -p 8080:8080 \
  -p 8081:8081 \
  -v protea-data:/app/data \
  -e PROTEA_ADMIN_PASSWORD="YourSecurePassword1!" \
  protea:latest
```

### Docker Compose - Basic

```yaml
# docker-compose.yml
version: '3.8'

services:
  protea:
    image: protea:latest
    container_name: protea
    ports:
      - "8080:8080"   # Web UI
      - "8081:8081"   # MCP SSE
    volumes:
      - protea-data:/app/data
    environment:
      - PROTEA_ADMIN_PASSWORD=YourSecurePassword1!
    restart: unless-stopped

volumes:
  protea-data:
```

### Docker Compose - Production with Traefik

```yaml
# docker-compose.yml
version: '3.8'

services:
  protea:
    image: protea:latest
    container_name: protea
    volumes:
      - protea-data:/app/data
    environment:
      - PROTEA_ADMIN_PASSWORD=${PROTEA_ADMIN_PASSWORD}
      - PROTEA_SESSION_HOURS=24
    labels:
      # Web UI
      - "traefik.enable=true"
      - "traefik.http.routers.protea-web.rule=Host(`protea.example.com`)"
      - "traefik.http.routers.protea-web.entrypoints=websecure"
      - "traefik.http.routers.protea-web.tls.certresolver=letsencrypt"
      - "traefik.http.services.protea-web.loadbalancer.server.port=8080"
      # MCP SSE
      - "traefik.http.routers.protea-sse.rule=Host(`protea.example.com`) && PathPrefix(`/sse`)"
      - "traefik.http.routers.protea-sse.entrypoints=websecure"
      - "traefik.http.routers.protea-sse.tls.certresolver=letsencrypt"
      - "traefik.http.services.protea-sse.loadbalancer.server.port=8081"
    restart: unless-stopped
    networks:
      - traefik

volumes:
  protea-data:

networks:
  traefik:
    external: true
```

### Docker Compose - With Environment File

```yaml
# docker-compose.yml
version: '3.8'

services:
  protea:
    image: protea:latest
    container_name: protea
    ports:
      - "8080:8080"
      - "8081:8081"
    volumes:
      - protea-data:/app/data
    env_file:
      - .env
    restart: unless-stopped

volumes:
  protea-data:
```

```bash
# .env
PROTEA_ADMIN_PASSWORD=YourSecurePassword1!
PROTEA_SESSION_HOURS=48
```

### Dockerfile (Build from Source)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY src/ src/

# Create data directory
RUN mkdir -p /app/data

# Expose ports
EXPOSE 8080 8081

# Default command runs both web and SSE servers
CMD ["sh", "-c", "protea-web & protea-sse"]
```

### Multi-Service Docker Compose (Separate Containers)

```yaml
# docker-compose.yml
version: '3.8'

services:
  protea-web:
    image: protea:latest
    container_name: protea-web
    command: protea-web
    ports:
      - "8080:8080"
    volumes:
      - protea-data:/app/data
    environment:
      - PROTEA_ADMIN_PASSWORD=${PROTEA_ADMIN_PASSWORD:-}
    restart: unless-stopped

  protea-sse:
    image: protea:latest
    container_name: protea-sse
    command: protea-sse
    ports:
      - "8081:8081"
    volumes:
      - protea-data:/app/data
    environment:
      - PROTEA_ADMIN_PASSWORD=${PROTEA_ADMIN_PASSWORD:-}
    restart: unless-stopped
    depends_on:
      - protea-web

volumes:
  protea-data:
```

---

## Development Mode

To disable authentication during development:

```bash
export PROTEA_AUTH_REQUIRED=false
protea-web
```

Or in docker-compose:

```yaml
environment:
  - PROTEA_AUTH_REQUIRED=false
```

**Warning:** Never disable authentication in production!

---

## Security Considerations

### Best Practices

1. **Use HTTPS in production** - API keys are sent in headers
2. **Use strong passwords** - Follow the complexity requirements
3. **Rotate API keys** - Create new keys periodically and revoke old ones
4. **Separate API keys per client** - Create unique keys for each MCP client
5. **Monitor last_used_at** - Check Settings to see when keys were last used
6. **Use environment files** - Don't hardcode passwords in docker-compose

### Network Security

For production deployments:

```yaml
# docker-compose.yml with internal network
services:
  protea:
    # ... other config
    networks:
      - internal
      - traefik

  # Only expose through reverse proxy

networks:
  internal:
    internal: true  # Not accessible from host
  traefik:
    external: true
```

### API Key Security

- API keys are stored as SHA-256 hashes in the database
- The plaintext key is only shown once at creation
- Revoked keys remain in the database for audit purposes
- Deleted keys are permanently removed

---

## Troubleshooting

### "Invalid API key" Error

1. Verify the key is correct (no extra spaces)
2. Check if the key has been revoked in Settings
3. Ensure the `Bearer ` prefix is included for SSE

### "Missing Authorization header" Error

Ensure your Claude Desktop config includes the Authorization header:

```json
"headers": {
  "Authorization": "Bearer prot_YOUR_KEY"
}
```

### "Authentication required but PROTEA_API_KEY not set" (Stdio)

For stdio transport, set the environment variable:

```json
"env": {
  "PROTEA_API_KEY": "prot_YOUR_KEY"
}
```

### Forgot Admin Password

If you've lost the admin password:

1. Stop Protea
2. Delete the database: `rm data/inventory.db`
3. Restart Protea - a new admin user will be created
4. Re-import any backed up data

Or manually reset via SQLite (advanced):

```bash
sqlite3 data/inventory.db
# Generate new bcrypt hash for 'NewPassword1!' and update
UPDATE users SET password_hash='$2b$12$...' WHERE username='admin';
```
