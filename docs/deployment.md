# Deployment Guide

## Development Workflow

```
1. Clone from GitHub
2. Create feature branch
3. Develop and test locally
4. Push branch, create PR → CI runs automatically
5. Merge PR to main
6. Tag release → Docker image published to GHCR
7. Pull image in production
```

## Local Development

```bash
# Clone
git clone https://github.com/rmaxseiner/protea.git
cd protea

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run locally
protea-web
```

## Local Docker Testing

Build and test with Docker before creating a PR:

```bash
# Build image locally
docker build -t protea:local .

# Run test instance
docker run -d \
  -p 8090:8080 \
  -v ./test-data:/data \
  --name protea-test \
  protea:local

# Verify it works
curl http://localhost:8090/

# Clean up
docker stop protea-test && docker rm protea-test
```

## Creating a Release

After your PR is merged to main:

```bash
# Tag the release
git checkout main
git pull
git tag -a v1.2.3 -m "Release v1.2.3: Brief description"
git push origin v1.2.3
```

GitHub Actions will automatically:
1. Run tests
2. Build Docker image
3. Push to `ghcr.io/rmaxseiner/protea:latest` and `ghcr.io/rmaxseiner/protea:1.2.3`
4. Create GitHub Release with auto-generated notes

## Production Deployment

Pull the latest release:

```bash
# On your production server
docker pull ghcr.io/rmaxseiner/protea:latest

# Or a specific version
docker pull ghcr.io/rmaxseiner/protea:1.2.3
```

Example docker-compose.yml:

```yaml
services:
  protea:
    image: ghcr.io/rmaxseiner/protea:latest
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data/db:/data/db
      - ./data/images:/data/images
    environment:
      - PROTEA_SECURE_COOKIES=true
```

## CI/CD

| Event | What Happens |
|-------|--------------|
| PR to main | Tests run on GitHub-hosted runners |
| Push to main | Tests run |
| Tag `v*` | Tests + build Docker image + push to GHCR + create Release |
