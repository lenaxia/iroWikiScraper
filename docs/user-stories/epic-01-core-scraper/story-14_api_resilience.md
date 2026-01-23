# Story 14: API Resilience and Version Compatibility

**Epic**: Epic 01 - Core Scraper Implementation  
**Story ID**: epic-01-story-14  
**Priority**: High (Production Readiness)  
**Status**: Not Started  
**Estimated Effort**: 1-2 days  
**Assignee**: TBD

## User Story

As a **scraper maintainer**,  
I want **robust protection against MediaWiki API changes and version upgrades**,  
So that **the scraper continues working reliably even when MediaWiki or the wiki changes**.

## Description

Enhance the API client and response parsing with defensive validation, API version detection, and graceful degradation to protect against MediaWiki upgrades, API changes, and response schema modifications. This ensures long-term maintainability and reduces brittleness.

## Background & Context

**Current Vulnerabilities:**
1. Direct dictionary access (`page_data["pageid"]`) will crash on field renames
2. No API version detection or compatibility checking
3. Brittle continuation token handling
4. No validation of response structure
5. No monitoring of API deprecation warnings

**MediaWiki Stability:**
- Core APIs (query, allpages) have been stable since 2006
- Deprecation warnings given years in advance
- But changes DO happen (field renames, new requirements, format changes)

**Risk Scenarios:**
- MediaWiki 1.45+ changes field names or continuation format
- iRO Wiki upgrades MediaWiki versions during our scraping
- API adds new required parameters
- Response structure changes subtly

## Acceptance Criteria

### 1. API Version Detection
- [ ] Detect MediaWiki version on client initialization
- [ ] Log version with INFO level
- [ ] Warn if version differs from tested versions
- [ ] Store version in client for reference
- [ ] Add version to error context

### 2. Response Structure Validation
- [ ] Create validation helper for required fields
- [ ] Validate all API responses before parsing
- [ ] Clear error messages showing what's missing
- [ ] Include full response data in error logs
- [ ] Add response schema to exceptions

### 3. Defensive Field Access
- [ ] Add `_safe_get()` helper for required fields
- [ ] Replace direct dict access in critical paths
- [ ] Validate field types (int, str, etc.)
- [ ] Handle missing optional fields gracefully
- [ ] Log warnings for unexpected fields

### 4. Continuation Token Validation
- [ ] Validate continuation token structure
- [ ] Check for unexpected token format
- [ ] Graceful fallback if format changed
- [ ] Log detailed continuation token info
- [ ] Test with various token formats

### 5. API Warning Monitoring
- [ ] Track unique API warnings
- [ ] Log NEW warnings prominently
- [ ] Collect warnings for analysis
- [ ] Optional: Save warnings to database
- [ ] Add warning count to statistics

### 6. Testing
- [ ] Test with missing required fields
- [ ] Test with renamed fields
- [ ] Test with changed continuation format
- [ ] Test with unknown API version
- [ ] Test with malformed responses
- [ ] Test graceful degradation

## Tasks

### Test Infrastructure (FIRST)
- [ ] Create fixtures for malformed responses
- [ ] Create fixtures for version detection
- [ ] Create fixtures for missing fields
- [ ] Create fixtures for changed formats

### Implementation
- [ ] Add API version detection to MediaWikiAPIClient
- [ ] Create response validation helpers
- [ ] Add defensive field access helpers
- [ ] Update PageDiscovery with validation
- [ ] Update all response parsing with safe access
- [ ] Add warning tracking system

### Testing
- [ ] Write tests in `tests/test_api_resilience.py`
- [ ] Test all validation scenarios
- [ ] Test version detection
- [ ] Run tests with various response formats

## Technical Details

### 1. API Version Detection

```python
# scraper/api/client.py

class MediaWikiAPIClient:
    def __init__(self, base_url: str, ...):
        # ... existing code ...
        self.api_version: Optional[str] = None
        self.api_version_detected = False
        
        # Detect version on first use (lazy)
        # Or detect immediately if check_version=True parameter
    
    def _detect_api_version(self) -> None:
        """Detect MediaWiki version and validate compatibility."""
        if self.api_version_detected:
            return
        
        try:
            response = self.query({
                "meta": "siteinfo",
                "siprop": "general"
            })
            
            general = response.get("query", {}).get("general", {})
            self.api_version = general.get("generator", "Unknown")
            
            logger.info(f"MediaWiki version: {self.api_version}")
            
            # Check if version is tested/supported
            tested_versions = ["1.44", "1.45", "1.46"]
            if not any(v in self.api_version for v in tested_versions):
                logger.warning(
                    f"Untested MediaWiki version: {self.api_version}. "
                    f"Scraper tested on: {', '.join(tested_versions)}. "
                    f"Some features may not work correctly."
                )
            
            self.api_version_detected = True
            
        except Exception as e:
            logger.warning(
                f"Could not detect MediaWiki version: {e}. "
                f"Proceeding without version check."
            )
            self.api_version = "Unknown"
            self.api_version_detected = True
```

### 2. Response Validation Helper

```python
# scraper/api/validation.py

from typing import Any, Dict, List, Optional, Type
from scraper.api.exceptions import APIResponseError

class ResponseValidator:
    """Validates MediaWiki API response structure."""
    
    @staticmethod
    def validate_required_fields(
        data: Dict[str, Any],
        required_fields: List[str],
        context: str = "response"
    ) -> None:
        """Validate that all required fields are present.
        
        Args:
            data: Dictionary to validate
            required_fields: List of required field names
            context: Description of what's being validated (for error messages)
            
        Raises:
            APIResponseError: If any required fields are missing
        """
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            logger.error(
                f"Missing required fields in {context}: {missing}",
                extra={
                    'missing_fields': missing,
                    'available_fields': list(data.keys()),
                    'full_data': data
                }
            )
            raise APIResponseError(
                f"API response missing required fields: {missing}",
                request_params={'context': context, 'missing': missing}
            )
    
    @staticmethod
    def safe_get(
        data: Dict[str, Any],
        field: str,
        expected_type: Type,
        context: str = "response"
    ) -> Any:
        """Safely get field with type validation.
        
        Args:
            data: Dictionary to get field from
            field: Field name
            expected_type: Expected Python type
            context: Description for error messages
            
        Returns:
            Field value
            
        Raises:
            APIResponseError: If field missing or wrong type
        """
        if field not in data:
            logger.error(
                f"Missing field '{field}' in {context}",
                extra={'available_fields': list(data.keys()), 'data': data}
            )
            raise APIResponseError(
                f"Missing required field: {field}",
                request_params={'context': context, 'field': field}
            )
        
        value = data[field]
        
        if not isinstance(value, expected_type):
            logger.error(
                f"Field '{field}' has wrong type in {context}. "
                f"Expected {expected_type.__name__}, got {type(value).__name__}",
                extra={'field': field, 'value': value, 'data': data}
            )
            raise APIResponseError(
                f"Field '{field}' has wrong type: "
                f"expected {expected_type.__name__}, got {type(value).__name__}",
                request_params={'context': context, 'field': field}
            )
        
        return value
```

### 3. Updated PageDiscovery with Validation

```python
# scraper/scrapers/page_scraper.py

from scraper.api.validation import ResponseValidator

class PageDiscovery:
    def discover_namespace(self, namespace: int) -> List[Page]:
        """Discover all pages in a specific namespace."""
        pages = []
        continue_params: Optional[Dict[str, Any]] = None
        
        # Detect API version on first use
        if not self.api.api_version_detected:
            self.api._detect_api_version()
        
        logger.info(f"Starting discovery for namespace {namespace}")
        
        while True:
            params = {
                'list': 'allpages',
                'aplimit': self.page_limit,
                'apnamespace': namespace,
            }
            
            if continue_params:
                # Validate continuation token format
                if not isinstance(continue_params, dict):
                    logger.error(
                        f"Invalid continuation token format: {type(continue_params)}. "
                        f"Expected dict, got {type(continue_params).__name__}"
                    )
                    raise APIResponseError(
                        f"Invalid continuation token format: {type(continue_params)}",
                        request_params={'continue_params': continue_params}
                    )
                params.update(continue_params)
            
            response = self.api.query(params)
            
            # Validate response structure
            query = response.get('query')
            if not query:
                logger.error(
                    "Response missing 'query' field",
                    extra={'response': response}
                )
                raise APIResponseError(
                    "API response missing 'query' field",
                    request_params=params
                )
            
            page_list = query.get('allpages', [])
            
            for page_data in page_list:
                try:
                    page = self._parse_page_data(page_data)
                    pages.append(page)
                except APIResponseError as e:
                    # Log error but continue with other pages
                    logger.error(
                        f"Failed to parse page data: {e}",
                        extra={'page_data': page_data},
                        exc_info=True
                    )
                    continue
            
            # Log progress
            if len(pages) % self.progress_interval == 0 or len(pages) < self.progress_interval:
                logger.info(f"Namespace {namespace}: {len(pages)} pages discovered")
            
            # Check for continuation
            if 'continue' not in response:
                break
            
            continue_params = response['continue']
        
        logger.info(f"Namespace {namespace} complete: {len(pages)} total pages")
        return pages
    
    def _parse_page_data(self, page_data: Dict[str, Any]) -> Page:
        """Parse page data with validation.
        
        Args:
            page_data: Raw page data from API
            
        Returns:
            Validated Page object
            
        Raises:
            APIResponseError: If page data is invalid
        """
        # Validate required fields
        ResponseValidator.validate_required_fields(
            page_data,
            required_fields=['pageid', 'ns', 'title'],
            context='page data'
        )
        
        # Safely extract fields with type validation
        page_id = ResponseValidator.safe_get(page_data, 'pageid', int, 'page data')
        namespace = ResponseValidator.safe_get(page_data, 'ns', int, 'page data')
        title = ResponseValidator.safe_get(page_data, 'title', str, 'page data')
        
        # Optional field - safe presence check
        is_redirect = 'redirect' in page_data
        
        return Page(
            page_id=page_id,
            namespace=namespace,
            title=title,
            is_redirect=is_redirect
        )
```

### 4. API Warning Tracking

```python
# scraper/api/client.py

class MediaWikiAPIClient:
    def __init__(self, ...):
        # ... existing code ...
        self.api_warnings_seen: Set[str] = set()
        self.warning_count = 0
    
    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse and validate API response with warning tracking."""
        # ... existing parsing code ...
        
        # Track and log warnings
        if 'warnings' in data:
            for warning_type, warning_data in data['warnings'].items():
                # Create unique warning signature
                warning_sig = f"{warning_type}:{str(warning_data)[:100]}"
                
                if warning_sig not in self.api_warnings_seen:
                    # NEW warning - log prominently
                    self.api_warnings_seen.add(warning_sig)
                    self.warning_count += 1
                    
                    logger.warning(
                        f"NEW API WARNING #{self.warning_count}: {warning_type}",
                        extra={
                            'warning_type': warning_type,
                            'warning_data': warning_data,
                            'warning_number': self.warning_count
                        }
                    )
                else:
                    # Known warning - debug level
                    logger.debug(
                        f"API warning (known): {warning_type}",
                        extra={'warning_type': warning_type}
                    )
        
        return data
    
    def get_warning_summary(self) -> Dict[str, Any]:
        """Get summary of API warnings encountered.
        
        Returns:
            Dictionary with warning statistics
        """
        return {
            'total_unique_warnings': len(self.api_warnings_seen),
            'warnings': list(self.api_warnings_seen),
            'api_version': self.api_version
        }
```

### 5. Test Examples

```python
# tests/test_api_resilience.py

import pytest
from scraper.api.client import MediaWikiAPIClient
from scraper.api.validation import ResponseValidator
from scraper.api.exceptions import APIResponseError
from scraper.scrapers.page_scraper import PageDiscovery

class TestAPIVersionDetection:
    """Test MediaWiki version detection."""
    
    def test_version_detection_success(self, api_client, mock_session):
        """Test successful version detection."""
        version_response = {
            "query": {
                "general": {
                    "generator": "MediaWiki 1.44.0"
                }
            }
        }
        
        mock_session.set_response_sequence([MockResponse(200, json_data=version_response)])
        
        api_client._detect_api_version()
        
        assert api_client.api_version == "MediaWiki 1.44.0"
        assert api_client.api_version_detected is True
    
    def test_version_detection_warns_on_unknown(self, api_client, mock_session, caplog):
        """Test warning on unknown version."""
        version_response = {
            "query": {
                "general": {
                    "generator": "MediaWiki 1.50.0"  # Future version
                }
            }
        }
        
        mock_session.set_response_sequence([MockResponse(200, json_data=version_response)])
        
        api_client._detect_api_version()
        
        assert "Untested MediaWiki version" in caplog.text
        assert "1.50.0" in caplog.text


class TestResponseValidation:
    """Test response structure validation."""
    
    def test_validate_required_fields_success(self):
        """Test validation passes with all fields present."""
        data = {'pageid': 1, 'ns': 0, 'title': 'Test'}
        
        # Should not raise
        ResponseValidator.validate_required_fields(
            data,
            required_fields=['pageid', 'ns', 'title'],
            context='test'
        )
    
    def test_validate_required_fields_missing(self):
        """Test validation fails with missing fields."""
        data = {'pageid': 1, 'ns': 0}  # Missing 'title'
        
        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_required_fields(
                data,
                required_fields=['pageid', 'ns', 'title'],
                context='test'
            )
        
        error = exc_info.value
        assert 'title' in str(error)
        assert 'missing' in str(error).lower()
    
    def test_safe_get_success(self):
        """Test safe_get with correct type."""
        data = {'pageid': 123, 'title': 'Test'}
        
        value = ResponseValidator.safe_get(data, 'pageid', int, 'test')
        assert value == 123
    
    def test_safe_get_wrong_type(self):
        """Test safe_get fails with wrong type."""
        data = {'pageid': '123'}  # String instead of int
        
        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.safe_get(data, 'pageid', int, 'test')
        
        error = exc_info.value
        assert 'wrong type' in str(error).lower()
        assert 'str' in str(error)


class TestPageDiscoveryResilience:
    """Test PageDiscovery with API resilience."""
    
    def test_parse_page_data_valid(self):
        """Test parsing valid page data."""
        discovery = PageDiscovery(api_client)
        
        page_data = {
            'pageid': 1,
            'ns': 0,
            'title': 'Main Page',
            'redirect': ''
        }
        
        page = discovery._parse_page_data(page_data)
        
        assert page.page_id == 1
        assert page.namespace == 0
        assert page.title == 'Main Page'
        assert page.is_redirect is True
    
    def test_parse_page_data_missing_field(self):
        """Test parsing fails gracefully with missing field."""
        discovery = PageDiscovery(api_client)
        
        page_data = {
            'pageid': 1,
            'ns': 0
            # Missing 'title'
        }
        
        with pytest.raises(APIResponseError) as exc_info:
            discovery._parse_page_data(page_data)
        
        error = exc_info.value
        assert 'title' in str(error)
    
    def test_discover_namespace_invalid_continuation(self, api_client, mock_session):
        """Test handling of invalid continuation token format."""
        # First response with invalid continuation format
        bad_continue_response = {
            "query": {"allpages": []},
            "continue": "invalid_string_format"  # Should be dict
        }
        
        mock_session.set_response_sequence([MockResponse(200, json_data=bad_continue_response)])
        
        discovery = PageDiscovery(api_client)
        
        # Should raise APIResponseError with clear message
        with pytest.raises(APIResponseError) as exc_info:
            list(discovery.discover_namespace(0))
        
        assert "continuation token" in str(exc_info.value).lower()


class TestAPIWarningTracking:
    """Test API warning tracking system."""
    
    def test_new_warning_logged_prominently(self, api_client, mock_session, caplog):
        """Test that new warnings are logged prominently."""
        import logging
        caplog.set_level(logging.WARNING)
        
        warning_response = {
            "warnings": {
                "main": {"*": "New warning message"}
            },
            "query": {"pages": {}}
        }
        
        mock_session.set_response_sequence([MockResponse(200, json_data=warning_response)])
        api_client.query({'list': 'allpages'})
        
        assert "NEW API WARNING" in caplog.text
        assert "main" in caplog.text
    
    def test_repeated_warning_not_duplicated(self, api_client, mock_session, caplog):
        """Test that repeated warnings are only logged once prominently."""
        import logging
        caplog.set_level(logging.WARNING)
        
        warning_response = {
            "warnings": {
                "main": {"*": "Same warning"}
            },
            "query": {"pages": {}}
        }
        
        mock_session.set_response_sequence([
            MockResponse(200, json_data=warning_response),
            MockResponse(200, json_data=warning_response)
        ])
        
        api_client.query({'list': 'allpages'})
        caplog.clear()
        api_client.query({'list': 'allpages'})
        
        # Second occurrence should not have "NEW" in warning log
        assert "NEW API WARNING" not in caplog.text
    
    def test_warning_summary(self, api_client, mock_session):
        """Test warning summary statistics."""
        warning_response = {
            "warnings": {
                "main": {"*": "Warning 1"},
                "query": {"*": "Warning 2"}
            },
            "query": {"pages": {}}
        }
        
        mock_session.set_response_sequence([MockResponse(200, json_data=warning_response)])
        api_client.query({'list': 'allpages'})
        
        summary = api_client.get_warning_summary()
        
        assert summary['total_unique_warnings'] == 2
        assert len(summary['warnings']) == 2
```

## Dependencies

### Requires
- Story 01: MediaWiki API Client
- Story 03: API Error Handling
- Story 04: Page Discovery

### Blocks
- None (enhancement of existing functionality)

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All tasks completed
- [ ] All tests passing (≥80% coverage)
- [ ] API version detection works
- [ ] Response validation implemented
- [ ] All direct dict access replaced with safe access
- [ ] Warning tracking functional
- [ ] Documentation complete
- [ ] Code reviewed
- [ ] Merged to main branch

## Notes for Implementation

### For New Developers

1. **Add validation gradually** - Start with critical paths (page parsing)
2. **Test with real API** - Verify against actual iRO Wiki responses
3. **Log everything** - Debug logs help diagnose API changes
4. **Make errors actionable** - Include full context in error messages

### Common Pitfalls

- Don't validate EVERYTHING (performance cost) - focus on critical paths
- Don't catch and ignore validation errors silently
- Don't assume API format will never change
- Don't skip version detection (it's fast)

### Testing Tips

- Create fixtures for various MediaWiki versions
- Test with both valid and invalid response formats
- Use real API integration tests monthly
- Mock time-based warning deduplication

## References

- MediaWiki API Stability: https://www.mediawiki.org/wiki/API:Main_page#Stability
- MediaWiki Deprecation Policy: https://www.mediawiki.org/wiki/Deprecation_policy
- API Version History: https://www.mediawiki.org/wiki/MediaWiki_1.44
