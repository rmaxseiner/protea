# Deployment Guide

This document describes the complete CI/CD workflow for Protea.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   Developer        GitHub                    server-container-01         │
│   ─────────        ──────                    ────────────────────        │
│                                                                          │
│   feature/* ──PR──► develop                                              │
│                       │                                                  │
│                       ▼                                                  │
│               ┌─────────────┐                                            │
│               │  CI Tests   │  (GitHub-hosted runner)                    │
│               └─────────────┘                                            │
│                       │                                                  │
│                       ▼                                                  │
│               ┌─────────────┐     ┌─────────────────────────────────┐   │
│               │ Build Image │────►│ ghcr.io/rmaxseiner/protea:develop│   │
│               └─────────────┘     └─────────────────────────────────┘   │
│                       │                          │                       │
│                       │                          ▼                       │
│                       │                 ┌───────────────┐                │
│                       └────────────────►│  TEST ENV     │                │
│                        (self-hosted     │  :8090        │                │
│                         runner)         │  /opt/protea- │                │
│                                         │  test         │                │
│                                         └───────────────┘                │
│                                                                          │
│   (when ready for release)                                               │
│                                                                          │
│   develop ──PR──► main                                                   │
│                     │                                                    │
│                     ▼                                                    │
│               Tag v1.2.3                                                 │
│                     │                                                    │
│                     ▼                                                    │
│               ┌─────────────┐     ┌─────────────────────────────────┐   │
│               │ Build Image │────►│ ghcr.io/rmaxseiner/protea:latest │   │
│               └─────────────┘     │ ghcr.io/rmaxseiner/protea:1.2.3  │   │
│                     │             └─────────────────────────────────┘   │
│                     │                          │                         │
│                     │                          ▼                         │
│                     │                 ┌───────────────┐                  │
│                     └────────────────►│  PROD ENV     │                  │
│                      (self-hosted     │  :8080        │                  │
│                       runner)         │  /opt/protea- │                  │
│                                       │  prod         │                  │
│                                       └───────────────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Environments

| Environment | URL | Image Tag | Branch | Purpose |
|-------------|-----|-----------|--------|---------|
| Development | localhost | local build | feature/* | Developer machines |
| Test/Staging | server-container-01:8090 | `:develop` | develop | Pre-release testing |
| Production | server-container-01:8080 | `:latest` | main + tag | Stable releases |

## Initial Setup

### 1. Create the `develop` Branch

```bash
git checkout -b develop
git push -u origin develop
```

### 2. Set Up GitHub Repository Settings

Go to **Settings → Branches** and add branch protection rules:

**For `main`:**
- Require pull request before merging
- Require status checks to pass (select "test" job)
- Require branches to be up to date

**For `develop`:**
- Require status checks to pass (select "test" job)

### 3. Configure GitHub Environments

Go to **Settings → Environments** and create:

**`staging`:**
- No special protection (auto-deploys on develop merge)

**`production`:**
- Add required reviewers (yourself)
- Optionally add wait timer for safety

### 4. Set Up Self-Hosted Runner on server-container-01

```bash
# SSH to server-container-01
ssh server-container-01

# Create runner directory
mkdir -p ~/actions-runner && cd ~/actions-runner

# Download runner (check https://github.com/actions/runner/releases for latest)
curl -o actions-runner-linux-x64.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-x64.tar.gz

# Configure runner
# Get the token from: GitHub repo → Settings → Actions → Runners → New self-hosted runner
./config.sh --url https://github.com/rmaxseiner/protea --token YOUR_TOKEN

# Install and start as service
sudo ./svc.sh install
sudo ./svc.sh start

# Verify it's running
sudo ./svc.sh status
```

### 5. Set Up Deployment Directories

On server-container-01:

```bash
# Test environment
sudo mkdir -p /opt/protea-test/data/{db,images}
sudo chown -R $USER:$USER /opt/protea-test
cp deploy/docker-compose.test.yml /opt/protea-test/docker-compose.yml

# Production environment
sudo mkdir -p /opt/protea-prod/data/{db,images}
sudo mkdir -p /opt/protea-prod/backups
sudo chown -R $USER:$USER /opt/protea-prod
cp deploy/docker-compose.prod.yml /opt/protea-prod/docker-compose.yml
```

### 6. Authenticate Docker with GHCR

On server-container-01, the runner needs to pull images:

```bash
# Create a Personal Access Token (classic) with read:packages scope
# GitHub → Settings → Developer settings → Personal access tokens

echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u rmaxseiner --password-stdin
```

## Daily Workflow

### Feature Development

```bash
# Start a feature
git checkout develop
git pull
git checkout -b feature/my-feature

# ... make changes ...

# Push and create PR to develop
git push -u origin feature/my-feature
# Create PR: feature/my-feature → develop
```

### Testing a Release

1. PR gets merged to `develop`
2. GitHub Actions automatically:
   - Runs tests
   - Builds `:develop` image
   - Deploys to test environment (port 8090)
3. Access http://server-container-01:8090 to verify
4. Test migrations by copying prod DB to test:
   ```bash
   # On server-container-01
   cp /opt/protea-prod/data/db/inventory.db /opt/protea-test/data/db/
   cd /opt/protea-test && docker compose restart
   ```

### Creating a Release

```bash
# Ensure develop is ready
git checkout develop
git pull

# Merge to main
git checkout main
git pull
git merge develop
git push

# Create release tag
git tag -a v1.2.3 -m "Release v1.2.3: Brief description"
git push origin v1.2.3
```

GitHub Actions will:
1. Build the image with tags `:latest`, `:1.2.3`, `:1.2`
2. Create a GitHub Release with auto-generated notes
3. Deploy to production (port 8080)
4. Backup the database before deployment

## Rollback

If a release has issues:

```bash
# On server-container-01
cd /opt/protea-prod

# Pull previous version
docker pull ghcr.io/rmaxseiner/protea:1.2.2  # previous version

# Update docker-compose.yml to use specific tag instead of :latest
# Then restart
docker compose down
docker compose up -d

# Restore database if needed
cp backups/inventory-YYYYMMDD-HHMMSS.db data/db/inventory.db
docker compose restart
```

## Monitoring

### Check deployment status
```bash
# Container status
docker ps | grep protea

# Logs
docker logs protea-prod -f
docker logs protea-test -f

# Health check
curl http://localhost:8080/
curl http://localhost:8090/
```

### Check GitHub Actions
- Go to https://github.com/rmaxseiner/protea/actions
- View workflow runs, logs, and status

## Secrets and Tokens

| Secret | Where | Purpose |
|--------|-------|---------|
| `GITHUB_TOKEN` | Automatic | Push to GHCR, create releases |
| `CODECOV_TOKEN` | GitHub Secrets (optional) | Code coverage reporting |
| GitHub PAT | server-container-01 docker login | Pull images from GHCR |
| Runner token | One-time setup | Register self-hosted runner |
