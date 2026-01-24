# Story 20: Publish to GHCR

**Story ID**: epic-06-story-20  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Low  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** user  
**I want** Docker images published to GitHub Container Registry  
**So that** I can easily pull and use the latest scraper images

## Acceptance Criteria

1. **Registry Configuration**
   - [ ] Publish to GitHub Container Registry (ghcr.io)
   - [ ] Repository configured for container packages
   - [ ] Proper permissions set
   - [ ] Public visibility enabled

2. **Automated Publishing**
   - [ ] Publish on main branch push
   - [ ] Publish on release creation
   - [ ] Tag with version numbers
   - [ ] Update `latest` tag

3. **Image Metadata**
   - [ ] Proper labels (OCI annotations)
   - [ ] Link to repository
   - [ ] License information
   - [ ] Build timestamp

4. **Documentation**
   - [ ] Pull instructions in README
   - [ ] Version tags explained
   - [ ] Example usage commands
   - [ ] Troubleshooting guide

## Technical Details

### GHCR Publishing Workflow

```yaml
name: Publish Docker Images

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  release:
    types: [ published ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write  # For provenance
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            # Tag with branch name
            type=ref,event=branch
            
            # Tag with semver
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            
            # Tag with commit SHA
            type=sha,prefix={{branch}}-
            
            # Latest tag for main branch
            type=raw,value=latest,enable={{is_default_branch}}
            
            # Date tag for releases
            type=schedule,pattern={{date 'YYYYMMDD'}}
          
          labels: |
            org.opencontainers.image.title=iRO Wiki Scraper
            org.opencontainers.image.description=Automated archival of the iRO Wiki
            org.opencontainers.image.vendor=${{ github.repository_owner }}
            org.opencontainers.image.licenses=MIT
            maintainer=${{ github.repository_owner }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          provenance: true  # SLSA provenance
          sbom: true  # Software Bill of Materials
      
      - name: Generate artifact attestation
        uses: actions/attest-build-provenance@v1
        with:
          subject-name: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true
      
      - name: Update package visibility
        run: |
          # Make package public
          gh api \
            --method PATCH \
            -H "Accept: application/vnd.github+json" \
            /user/packages/container/${{ github.event.repository.name }}/versions \
            -f visibility=public
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Add package to repository
        run: |
          # Link package to repository
          gh api \
            --method PUT \
            -H "Accept: application/vnd.github+json" \
            /user/packages/container/${{ github.event.repository.name }}/restore \
            -F repository_id=${{ github.event.repository.id }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Image Tagging Strategy

```
# Tag format explained:

ghcr.io/owner/repo:latest          # Always points to latest main build
ghcr.io/owner/repo:main            # Latest commit on main branch
ghcr.io/owner/repo:v1.2.3          # Specific release version
ghcr.io/owner/repo:v1.2            # Latest patch of minor version
ghcr.io/owner/repo:v1              # Latest minor of major version
ghcr.io/owner/repo:main-abc123     # Specific commit SHA
ghcr.io/owner/repo:20240124        # Build from specific date
```

### Package Permissions

```yaml
# .github/workflows/publish.yml
permissions:
  contents: read       # Read repository
  packages: write      # Publish to GHCR
  id-token: write      # Generate provenance
  attestations: write  # Publish attestations
```

### Usage Documentation

```markdown
## Docker Images

### Available Tags

- `latest` - Latest stable build from main branch
- `v1.2.3` - Specific release version
- `v1.2` - Latest patch of v1.2.x
- `v1` - Latest minor of v1.x.x
- `main` - Latest commit on main (may be unstable)

### Pull Image

```bash
# Latest release
docker pull ghcr.io/OWNER/REPO:latest

# Specific version
docker pull ghcr.io/OWNER/REPO:v1.0.0

# Development version
docker pull ghcr.io/OWNER/REPO:main
```

### Authentication

GHCR is public for public repositories. For private repositories:

```bash
# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Or use GitHub CLI
gh auth token | docker login ghcr.io -u USERNAME --password-stdin
```

### Verify Image

```bash
# Check image labels
docker inspect ghcr.io/OWNER/REPO:latest

# Verify provenance (requires Docker Buildx)
docker buildx imagetools inspect ghcr.io/OWNER/REPO:latest --format "{{json .Provenance}}"

# View SBOM
docker buildx imagetools inspect ghcr.io/OWNER/REPO:latest --format "{{json .SBOM}}"
```

### Multi-Architecture

Images support multiple architectures:
- `linux/amd64` - Intel/AMD x86_64
- `linux/arm64` - ARM 64-bit (Apple Silicon, AWS Graviton)

Docker automatically pulls the correct architecture:

```bash
# On Intel Mac/Linux
docker pull ghcr.io/OWNER/REPO:latest
# Pulls linux/amd64

# On Apple Silicon Mac
docker pull ghcr.io/OWNER/REPO:latest
# Pulls linux/arm64
```
```

### Package README

```markdown
# iRO Wiki Scraper Docker Image

Automated archival tool for the iRO Wiki with full history preservation.

## Quick Start

```bash
docker run -v $(pwd)/data:/data ghcr.io/OWNER/REPO:latest \
  python -m scraper scrape --database /data/irowiki.db
```

## Features

- ✅ Pre-built and ready to use
- ✅ Multi-architecture (amd64, arm64)
- ✅ Regular updates
- ✅ Verified provenance

## Documentation

See [GitHub repository](https://github.com/OWNER/REPO) for full documentation.

## License

MIT License - see [LICENSE](https://github.com/OWNER/REPO/blob/main/LICENSE)
```

### Cleanup Old Versions

```yaml
- name: Clean up old package versions
  uses: actions/delete-package-versions@v5
  with:
    package-name: ${{ github.event.repository.name }}
    package-type: 'container'
    min-versions-to-keep: 10
    delete-only-untagged-versions: 'true'
```

## Dependencies

- **Story 19**: Docker image build (builds images to publish)

## Implementation Notes

- GHCR is free for public repositories
- No separate authentication needed for public images
- Provenance and SBOM improve security
- Package visibility must be set to public
- Link package to repository for discoverability
- Consider storage limits (check pricing)
- Old untagged versions can be cleaned up
- Multi-architecture increases storage but improves compatibility

## Testing Requirements

- [ ] Test publishing to GHCR
- [ ] Test pulling published image
- [ ] Test different tags work correctly
- [ ] Test multi-architecture pulls
- [ ] Verify provenance attached
- [ ] Test package visibility is public
- [ ] Test pulling without authentication
- [ ] Test version cleanup works

## Definition of Done

- [ ] Publishing workflow created
- [ ] GHCR authentication configured
- [ ] Tagging strategy implemented
- [ ] Provenance and SBOM enabled
- [ ] Package visibility set to public
- [ ] Package linked to repository
- [ ] Documentation written
- [ ] Tested publishing and pulling
- [ ] Code reviewed and approved
