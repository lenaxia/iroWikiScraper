# Documentation

This directory contains all project documentation for the iRO-Wiki-Scraper project.

## Directory Structure

- **`design/`** - Technical design documents and architecture specifications
- **`worklog/`** - Daily work logs tracking progress, decisions, and blockers
- **`user-stories/`** - User stories organized by epic with acceptance criteria

## Documentation Standards

### File Naming Conventions

All documentation files follow date-based naming:

```
YYYY-MM-DD_NN_descriptive_name.md
```

Where:
- `YYYY-MM-DD` is the ISO 8601 date
- `NN` is a two-digit sequence number (01, 02, 03...) that resets daily
- `descriptive_name` is a brief, lowercase, hyphen-separated description

Examples:
- `2026-01-23_01_initial_architecture.md`
- `2026-01-23_02_database_schema.md`
- `2026-01-24_01_scraper_implementation.md`

### Document Types

#### Design Documents (`design/`)
- **Purpose**: Architecture, technical specifications, API designs
- **When**: Created before implementing major features
- **Contains**: System architecture, data models, API contracts, technical decisions
- **Audience**: Developers, architects, future maintainers

#### Worklog Entries (`worklog/`)
- **Purpose**: Track daily progress, decisions, and context
- **When**: After significant work sessions or before context switches
- **Contains**: What was done, decisions made, blockers encountered, next steps
- **Audience**: Team members, future self, project managers

#### User Stories (`user-stories/`)
- **Purpose**: Feature requirements and acceptance criteria
- **Organization**: Grouped by epic in subdirectories
- **Contains**: Story description, acceptance criteria, tasks, status
- **Audience**: Product owners, developers, stakeholders

## Quick Links

- [Design Documents](design/README.md) - Technical specifications
- [Work Logs](worklog/README.md) - Progress tracking
- [User Stories](user-stories/README.md) - Feature requirements

## Best Practices

1. **Write as you go**: Document decisions when they're fresh
2. **Be specific**: Include context, rationale, and alternatives considered
3. **Reference sources**: Link to relevant code, issues, or external docs
4. **Update status**: Keep story statuses and worklogs current
5. **Cross-reference**: Link related docs together for context
6. **Be concise**: Clear and direct writing, avoid unnecessary verbosity

## Markdown Standards

All documentation uses GitHub-flavored Markdown with:
- Clear hierarchical headings (H1 for title, H2 for sections)
- Code blocks with language tags for syntax highlighting
- Tables for structured data
- Lists for enumeration
- Links to related documents

## Version Control

- All documentation is version controlled with git
- Commit documentation changes with descriptive messages
- Review documentation in PRs alongside code changes
- Archive outdated docs rather than deleting them
