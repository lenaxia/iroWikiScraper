# Story 09: Internal Link Extraction

**Epic**: Epic 01  
**Story ID**: epic-01-story-09  
**Priority**: Medium  
**Effort**: 2 days

## User Story
As a scraper developer, I want to extract internal links from page content, so that wiki navigation structure is preserved.

## Acceptance Criteria
- [ ] Parse wikitext for [[Target]] links
- [ ] Parse wikitext for {{Template}} transclusions
- [ ] Parse wikitext for [[File:]] references
- [ ] Parse wikitext for [[Category:]] memberships
- [ ] Return Link objects: source_page_id, target_title, link_type

## Implementation
Use regex or mwparserfromhell library to parse wikitext.
Store links for later database insertion.
