# Design Documents

This directory contains technical design documents, architecture specifications, and API designs for the iRO-Wiki-Scraper project.

## Purpose

Design documents capture technical decisions, system architecture, and implementation specifications **before** code is written. They serve as:

1. **Planning tools**: Think through architecture before implementation
2. **Communication**: Share technical approach with team
3. **Reference**: Guide implementation and troubleshooting
4. **Historical record**: Document why decisions were made

## Naming Convention

```
YYYY-MM-DD_NN_descriptive_name.md
```

Examples:
- `2026-01-23_01_system_architecture.md`
- `2026-01-23_02_database_schema.md`
- `2026-01-24_01_api_client_design.md`

The `NN` counter resets to `01` each day.

## Document Structure

Each design document should include:

```markdown
# [Feature/Component Name]

**Date**: YYYY-MM-DD
**Author**: [Name]
**Status**: [Draft | Review | Approved | Implemented | Superseded]

## Overview

Brief description of what's being designed.

## Goals

- What problem does this solve?
- What are the requirements?
- What are the non-goals?

## Design

### Architecture

High-level system design with diagrams.

### Data Models

Schemas, types, interfaces.

### API Design

Function signatures, endpoints, request/response formats.

### Implementation Details

Key algorithms, formulas, edge cases.

## Alternatives Considered

What other approaches were evaluated and why they were rejected.

## Open Questions

Unresolved issues that need discussion.

## References

Links to related docs, external resources, prior art.
```

## Status Values

- **Draft**: Work in progress, not yet ready for review
- **Review**: Ready for team review and feedback
- **Approved**: Design approved, ready for implementation
- **Implemented**: Design has been implemented in code
- **Superseded**: Design replaced by newer document (link to replacement)

## When to Create

Create a design document when:
- Starting a new major feature or component
- Making significant architectural changes
- Designing public APIs or data schemas
- Solving complex technical problems
- Making decisions with long-term impact

Small bug fixes and minor tweaks don't need design docs.

## Best Practices

1. **Write before coding**: Design documents guide implementation
2. **Include diagrams**: ASCII art, Mermaid, or reference images
3. **Show alternatives**: Explain why you chose this approach
4. **Be specific**: Include code examples, schema definitions, API contracts
5. **Update status**: Mark as Implemented when done, Superseded if replaced
6. **Link to code**: Once implemented, link to relevant files

## Design Document Index

<!-- Maintain this list as documents are added -->

### Architecture
- *No documents yet*

### Database
- *No documents yet*

### Scraper
- *No documents yet*

### SDK
- *No documents yet*

### Infrastructure
- *No documents yet*

---

**Template**: Use the structure above as a template for new design documents.
