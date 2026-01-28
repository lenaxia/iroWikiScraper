# US-0707: Configuration Management

**Epic:** Epic 07 - CLI and Orchestration Layer  
**Status:** ✅ Complete  
**Priority:** Low  
**Story Points:** 2

## User Story

As a user, I need the CLI to load and merge configuration from files and command-line arguments, so that I can customize scraper behavior without editing code.

## Acceptance Criteria

1. **Configuration Sources**
   - [x] Built-in defaults from Config class
   - [x] YAML file via --config flag
   - [x] Command-line argument overrides

2. **Precedence Order**
   - [x] 1. Command-line arguments (highest priority)
   - [x] 2. Configuration file
   - [x] 3. Built-in defaults (lowest priority)

3. **CLI Arguments Override Config**
   - [x] --database overrides storage.database_file
   - [x] --rate-limit overrides scraper.rate_limit
   - [x] --log-level overrides logging.level

4. **Configuration Loading**
   - [x] Load from file if --config specified
   - [x] Handle missing config file gracefully (error message)
   - [x] Handle invalid YAML gracefully (error message)
   - [x] Use defaults if no config file specified

5. **Validation**
   - [x] Validate config after loading and merging
   - [x] Exit with clear error if validation fails
   - [x] Show which config value is invalid

## Technical Details

### Configuration Loading Function

```python
def _load_config(args: Namespace) -> Config:
    """Load configuration from file or use defaults.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Config instance with merged settings
    """
    # Load from file or use defaults
    if args.config:
        logger.info(f"Loading configuration from {args.config}")
        try:
            config = Config.from_yaml(args.config)
        except ConfigError as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)
    else:
        logger.info("Using default configuration")
        config = Config()
    
    # Override with CLI arguments
    if hasattr(args, "rate_limit") and args.rate_limit:
        config.scraper.rate_limit = args.rate_limit
    
    if args.database:
        config.storage.database_file = args.database
    
    if args.log_level:
        config.logging.level = args.log_level
    
    # Validate merged configuration
    try:
        config.validate()
    except ConfigError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)
    
    return config
```

### Example Configuration File

```yaml
# config.yaml
wiki:
  base_url: "https://irowiki.org"
  api_path: "/w/api.php"

scraper:
  rate_limit: 1.5
  timeout: 60
  max_retries: 5
  user_agent: "MyCustomBot/1.0"

storage:
  data_dir: "archive"
  database_file: "archive/wiki.db"

logging:
  level: "DEBUG"
  log_file: "logs/scraper.log"
```

### Example CLI Override

```bash
# Use config file but override rate limit and database
python -m scraper --config config.yaml --rate-limit 2.0 --database custom.db full
```

### Configuration Precedence Example

```
Built-in default:  rate_limit = 1.0
Config file:       rate_limit = 1.5
CLI argument:      --rate-limit 2.0

Result:            rate_limit = 2.0 (CLI wins)
```

## Dependencies

- `scraper.config.Config` and `ConfigError`
- `argparse.Namespace`

## Testing Requirements

- [x] Test loading config from file
- [x] Test using defaults when no config file
- [x] Test CLI arguments override config file
- [x] Test CLI arguments override defaults
- [x] Test missing config file shows error
- [x] Test invalid YAML shows error
- [x] Test invalid config values caught by validation

**Test File:** `tests/test_us0707_config_management.py` (25 tests, all passing)

## Implementation

**Implementation File:** `scraper/cli/commands.py:37-75` (`_load_config` function)

**Changes Made:**
1. Added `ConfigError` exception handling for file loading
2. Added `ConfigError` exception handling for validation
3. Both errors log and call `sys.exit(1)` for clean CLI exit

**Test Results:** ✅ 25/25 tests passing, 1281/1281 total tests passing

## Documentation

- [ ] Document configuration file format in README
- [ ] Document precedence order in README
- [ ] Provide example config.yaml file
- [ ] Document each configuration option

## Notes

- Configuration file is optional - defaults should work for most users
- CLI overrides allow quick adjustments without editing config file
- Validation ensures config is valid before starting scrape
