# Story 06: Generic Pagination Handler

**Epic**: Epic 01 - Core Scraper  
**Story ID**: epic-01-story-06  
**Priority**: Medium  
**Effort**: 2 days

## User Story
As a scraper developer, I want a reusable pagination handler, so that all API queries handle continuation consistently.

## Description
Create generic pagination utility that works with any MediaWiki API query using continue tokens.

## Acceptance Criteria
- [ ] PaginatedQuery class handles any API query
- [ ] Automatically follows continue tokens
- [ ] Yields results incrementally (generator)
- [ ] Configurable batch size
- [ ] Progress callback support

## Implementation
```python
class PaginatedQuery:
    def __init__(self, api_client, initial_params, result_path):
        self.api = api_client
        self.params = initial_params
        self.result_path = result_path  # e.g., ['query', 'allpages']
    
    def __iter__(self):
        continue_token = None
        while True:
            params = {**self.params}
            if continue_token:
                params.update(continue_token)
            
            response = self.api.query(params)
            
            # Extract results using path
            data = response
            for key in self.result_path:
                data = data[key]
            
            yield from data
            
            if 'continue' not in response:
                break
            continue_token = response['continue']

# Usage:
query = PaginatedQuery(api, {'list': 'allpages', 'aplimit': 500}, ['query', 'allpages'])
for page in query:
    process(page)
```

Dependencies: Story 01 (API Client)
