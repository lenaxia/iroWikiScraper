# User Stories

This directory contains user stories organized by epic for the iRO-Wiki-Scraper project.

## Purpose

User stories describe features and requirements from the user's perspective. They help:

1. **Define scope**: Clearly articulate what needs to be built
2. **Guide implementation**: Provide acceptance criteria for completion
3. **Track progress**: Organize work into manageable chunks
4. **Communicate value**: Explain why features matter

## Organization

User stories are grouped by **epic** (major feature area) in subdirectories:

```
user-stories/
├── README.md (this file)
├── epic-01-scraper/
│   ├── README.md (epic overview)
│   ├── story-01_page_discovery.md
│   ├── story-02_revision_scraping.md
│   └── ...
├── epic-02-database/
│   ├── README.md
│   ├── story-01_schema_design.md
│   └── ...
└── epic-03-sdk/
    ├── README.md
    └── ...
```

## Epic Structure

Each epic folder contains:
- `README.md` - Epic overview, goals, and story list
- `story-NN_description.md` - Individual story files

## Story Naming Convention

```
story-NN_brief_description.md
```

Examples:
- `story-01_page_discovery.md`
- `story-02_revision_scraping.md`
- `story-03_incremental_updates.md`

Story numbers are sequential within each epic.

## Story Structure

Each user story follows this format:

```markdown
# Story: [Title]

**Epic**: [Epic Name]
**Story ID**: [epic-NN-story-NN]
**Priority**: [High | Medium | Low]
**Status**: [Not Started | In Progress | Blocked | Completed]
**Estimate**: [Time estimate]

## User Story

As a [user type],
I want [goal/desire],
So that [benefit/value].

## Description

Detailed explanation of the feature or requirement.

## Acceptance Criteria

- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2
- [ ] Specific, testable criterion 3

## Tasks

- [ ] Technical task 1
- [ ] Technical task 2
- [ ] Write tests
- [ ] Update documentation

## Dependencies

- Depends on: [story-NN_name]
- Blocks: [story-NN_name]

## Notes

Additional context, constraints, or considerations.

## References

- Design doc: [link]
- Related issue: [link]
- External reference: [link]
```

## Status Values

- **Not Started**: Story defined but work hasn't begun
- **In Progress**: Actively being worked on
- **Blocked**: Cannot proceed due to dependency
- **Completed**: All acceptance criteria met, tests passing

## Priority Levels

- **High**: Critical path, must be done soon
- **Medium**: Important but not urgent
- **Low**: Nice to have, can be deferred

## Acceptance Criteria

Good acceptance criteria are:
- **Specific**: Clear, unambiguous
- **Testable**: Can verify completion
- **Independent**: Not dependent on other criteria
- **Valuable**: Delivers user benefit

Example of good criteria:
- ✅ "Scraper fetches all revisions for a given page, paginating automatically"
- ✅ "Database stores revision content with timestamp, author, and comment"
- ✅ "API returns 404 error with clear message for non-existent pages"

Example of bad criteria:
- ❌ "Scraper works correctly" (not specific or testable)
- ❌ "System is performant" (subjective, not measurable)

## Epic List

### Epic 01: Core Scraper Implementation
**Location**: [epic-01-core-scraper/](epic-01-core-scraper/)  
**Goal**: Implement MediaWiki API scraper with full revision history  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Stories**: 13  
**Effort**: 2-3 weeks

### Epic 02: Database & Storage
**Location**: [epic-02-database-storage/](epic-02-database-storage/)  
**Goal**: Design and implement database schema for complete archival  
**Priority**: High (Critical Path)  
**Status**: Not Started  
**Stories**: 15  
**Effort**: 1-2 weeks

### Epic 03: Incremental Updates
**Location**: [epic-03-incremental-updates/](epic-03-incremental-updates/)  
**Goal**: Implement incremental scraping for efficient monthly updates  
**Priority**: High  
**Status**: Not Started  
**Stories**: 13  
**Effort**: 1-2 weeks

### Epic 04: Export & Packaging
**Location**: [epic-04-export-packaging/](epic-04-export-packaging/)  
**Goal**: MediaWiki XML export and release packaging  
**Priority**: Medium  
**Status**: Not Started  
**Stories**: 13  
**Effort**: 1 week

### Epic 05: Go SDK
**Location**: [epic-05-go-sdk/](epic-05-go-sdk/)  
**Goal**: Build Go SDK for querying archived wiki data  
**Priority**: Medium  
**Status**: Not Started  
**Stories**: 23  
**Effort**: 2 weeks

### Epic 06: Automation & CI/CD
**Location**: [epic-06-automation-cicd/](epic-06-automation-cicd/)  
**Goal**: Automate monthly scraping and release publishing  
**Priority**: Medium  
**Status**: Not Started  
**Stories**: 20  
**Effort**: 1 week

---

**Total Stories**: 97  
**Total Estimated Effort**: 8-11 weeks

---

**Template**: Use the story structure above as a template for new user stories.
