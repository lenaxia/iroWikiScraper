# Story 19: Docker Image Build

**Story ID**: epic-06-story-19  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Low  
**Estimate**: 3 hours  
**Status**: Not Started

## User Story

**As a** user  
**I want** pre-built Docker images for the scraper  
**So that** I can easily run the scraper without setting up Python/dependencies

## Acceptance Criteria

1. **Dockerfile**
   - [ ] Multi-stage build for optimal size
   - [ ] Python 3.11 base image
   - [ ] All dependencies installed
   - [ ] Scraper installed and working

2. **Image Build**
   - [ ] Build on every push to main
   - [ ] Build on release creation
   - [ ] Multi-architecture (amd64, arm64)
   - [ ] Optimized layer caching

3. **Image Variants**
   - [ ] Slim image (scraper only)
   - [ ] Full image (with tools)
   - [ ] Development image (with dev dependencies)
   - [ ] Tagged versions

4. **Testing**
   - [ ] Test image builds successfully
   - [ ] Test scraper runs in container
   - [ ] Test volume mounts
   - [ ] Test environment variables

## Technical Details

### Dockerfile

```dockerfile
# Multi-stage build for optimal size

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy source code
COPY . .
RUN pip install --user --no-cache-dir -e .

# Stage 2: Runtime
FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.description="iRO Wiki Scraper"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application
COPY --from=builder /build /app

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Create directories for data
RUN mkdir -p /data /downloads /logs

# Set volumes
VOLUME ["/data", "/downloads", "/logs"]

# Default command
CMD ["python", "-m", "scraper", "--help"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  scraper:
    build: .
    image: ghcr.io/OWNER/REPO:latest
    container_name: irowiki-scraper
    volumes:
      - ./data:/data
      - ./downloads:/downloads
      - ./logs:/logs
    environment:
      - DATABASE_PATH=/data/irowiki.db
      - LOG_LEVEL=INFO
    command: >
      python -m scraper scrape
      --config /data/config.yaml
      --incremental
  
  # Optional: PostgreSQL backend
  postgres:
    image: postgres:15
    container_name: irowiki-postgres
    environment:
      POSTGRES_DB: irowiki
      POSTGRES_USER: scraper
      POSTGRES_PASSWORD: password
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres-data:
```

### Build Workflow

```yaml
name: Build Docker Images

on:
  push:
    branches: [ main ]
  release:
    types: [ published ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to GitHub Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=sha
            type=raw,value=latest,enable={{is_default_branch}}
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Test image
        if: github.event_name == 'pull_request'
        run: |
          docker run --rm ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:pr-${{ github.event.number }} \
            python -m scraper --version
```

### Multi-variant Builds

```dockerfile
# Dockerfile.slim - Minimal image
FROM python:3.11-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scraper/ ./scraper/
CMD ["python", "-m", "scraper"]

# Dockerfile.dev - Development image
FROM python:3.11
WORKDIR /app
RUN apt-get update && apt-get install -y vim git
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt
COPY . .
CMD ["/bin/bash"]
```

### Usage Documentation

```markdown
## Docker Usage

### Pull Image

```bash
docker pull ghcr.io/OWNER/REPO:latest
```

### Run Scraper

```bash
# Basic usage
docker run -v $(pwd)/data:/data ghcr.io/OWNER/REPO:latest \
  python -m scraper scrape --database /data/irowiki.db

# With configuration
docker run \
  -v $(pwd)/data:/data \
  -v $(pwd)/config.yaml:/app/config.yaml \
  ghcr.io/OWNER/REPO:latest \
  python -m scraper scrape --config /app/config.yaml

# Interactive shell
docker run -it --rm ghcr.io/OWNER/REPO:latest /bin/bash
```

### Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f scraper

# Stop services
docker-compose down
```

### Build Locally

```bash
# Build image
docker build -t irowiki-scraper .

# Build specific variant
docker build -f Dockerfile.slim -t irowiki-scraper:slim .

# Build for ARM (on M1 Mac)
docker build --platform linux/arm64 -t irowiki-scraper:arm64 .
```

### Environment Variables

- `DATABASE_PATH`: Path to SQLite database (default: `/data/irowiki.db`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `RATE_LIMIT`: Requests per second (default: `2`)
```

## Dependencies

- None (Docker is self-contained)

## Implementation Notes

- Use multi-stage builds to reduce image size
- Alpine images are smaller but may have compatibility issues
- Use BuildKit for faster builds and caching
- Tag with version numbers for reproducibility
- Test images before publishing
- Document volume mounts clearly
- Consider security scanning (Trivy, Snyk)
- Keep base images up to date

## Testing Requirements

- [ ] Test image builds successfully
- [ ] Test scraper runs in container
- [ ] Test with volume mounts
- [ ] Test with environment variables
- [ ] Test multi-architecture builds
- [ ] Test on Linux, macOS, Windows
- [ ] Test docker-compose setup
- [ ] Test slim variant

## Definition of Done

- [ ] Dockerfile created
- [ ] Docker Compose file created
- [ ] Build workflow implemented
- [ ] Multi-architecture builds working
- [ ] Image variants created
- [ ] Documentation written
- [ ] Tested locally and in CI
- [ ] Code reviewed and approved
