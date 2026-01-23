# Story 13: Configuration Management

**Epic**: Epic 01  
**Story ID**: epic-01-story-13  
**Priority**: High  
**Effort**: 2 days

## User Story
As a user, I want to configure the scraper via YAML file, so that I can customize behavior without changing code.

## Acceptance Criteria
- [ ] Load config from config.yaml
- [ ] Support: base_url, rate_limit, timeout, user_agent, max_retries
- [ ] Support: data_dir, checkpoint_file, log_level
- [ ] Validate config on load
- [ ] Provide sensible defaults
- [ ] Example config file

## Implementation
```python
# scraper/config.py
import yaml
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    # Wiki
    base_url: str = "https://irowiki.org"
    
    # Rate limiting
    rate_limit: float = 1.0  # requests per second
    
    # HTTP
    timeout: int = 30
    max_retries: int = 3
    user_agent: str = "iROWikiArchiver/1.0"
    
    # Storage
    data_dir: Path = Path("data")
    checkpoint_file: Path = Path("data/.checkpoint")
    
    # Logging
    log_level: str = "INFO"
    
    @classmethod
    def from_yaml(cls, path: str):
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def validate(self):
        if self.rate_limit <= 0:
            raise ValueError("rate_limit must be positive")
        # ... more validation

# config.example.yaml
wiki:
  base_url: "https://irowiki.org"

scraper:
  rate_limit: 1.0
  timeout: 30
  max_retries: 3

storage:
  data_dir: "data"
  checkpoint_file: "data/.checkpoint"

logging:
  level: "INFO"
```
