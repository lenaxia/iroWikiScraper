# US-0708 Validation Report - GitHub Actions Integration

**Date:** 2026-01-24  
**Status:** ❌ FAILED - Critical gaps found  
**Severity:** HIGH - Workflows will not execute correctly

---

## Executive Summary

The GitHub Actions workflows DO NOT match the CLI implementation. The workflows use non-existent commands and flags that will cause immediate failures when executed.

**Critical Issues:**
1. Workflows use `python -m scraper scrape` (non-existent subcommand)
2. Workflows use `--force-full` and `--incremental` flags (don't exist)
3. Workflow input names don't match user story specification
4. CLI doesn't provide all flags that workflows expect

---

## Acceptance Criteria Validation

### 1. Monthly Scrape Workflow ❌ FAILED

**Requirement:** Update to use `python -m scraper incremental`

**Current Implementation (Line 202-223):**
```yaml
- name: Run incremental scrape
  run: |
    SCRAPER_CMD="python -m scraper scrape"  # ❌ 'scrape' subcommand doesn't exist
    SCRAPER_CMD="$SCRAPER_CMD --config config.yaml"
    SCRAPER_CMD="$SCRAPER_CMD --database data/irowiki.db"
    SCRAPER_CMD="$SCRAPER_CMD --log-level INFO"
    
    if [[ "${{ steps.scrape-params.outputs.scrape_type }}" == "full" ]]; then
      SCRAPER_CMD="$SCRAPER_CMD --force-full"  # ❌ Flag doesn't exist
    else
      SCRAPER_CMD="$SCRAPER_CMD --incremental"  # ❌ Flag doesn't exist
    fi
```

**Expected Implementation:**
```yaml
- name: Run incremental scrape
  run: |
    python -m scraper incremental \
      --config config.yaml \
      --database data/irowiki.db \
      --log-level INFO
```

**Issues:**
- Uses non-existent `scrape` subcommand
- Uses non-existent `--force-full` flag
- Uses non-existent `--incremental` flag
- Overly complex command construction

**Status:** ❌ FAILED

---

### 2. Manual Scrape Workflow ❌ FAILED

**Requirement:** Support both full and incremental scrapes with proper commands

**Current Implementation (Line 123-145):**
```yaml
- name: Run scraper
  run: |
    CMD="python -m scraper scrape --config config.yaml"  # ❌ Wrong
    
    if [[ "${{ github.event.inputs.scrape_type }}" == "full" ]]; then
      CMD="$CMD --force-full"  # ❌ Flag doesn't exist
    else
      CMD="$CMD --incremental"  # ❌ Flag doesn't exist
    fi
    
    if [[ "${{ github.event.inputs.force }}" == "true" ]]; then
      CMD="$CMD --force"
    fi
```

**Expected Implementation:**
```yaml
- name: Run full scrape
  if: ${{ inputs.incremental == false }}
  run: |
    if [ "${{ inputs.force }}" == "true" ]; then
      python -m scraper full --force --config config.yaml --database data/irowiki.db
    else
      python -m scraper full --config config.yaml --database data/irowiki.db
    fi

- name: Run incremental scrape
  if: ${{ inputs.incremental == true }}
  run: |
    python -m scraper incremental --config config.yaml --database data/irowiki.db
```

**Issues:**
- Uses non-existent `scrape` subcommand
- Uses non-existent `--force-full` and `--incremental` flags
- Doesn't separate full vs incremental into different steps

**Status:** ❌ FAILED

---

### 3. Workflow Inputs ⚠️ PARTIAL

**Requirement:** Workflows should have these inputs:
- `incremental` (boolean, default: true)
- `force` (boolean, default: false)
- `create_release` (boolean, default: false)
- `announce` (boolean, default: false)
- `reason` (string, optional)

**Monthly Workflow Inputs:**
```yaml
scrape_type:          # ❌ Should be 'incremental' boolean
  type: choice
  options:
    - incremental
    - full
force: ✅             # Correct
create_release: ✅    # Correct
announce: ✅          # Correct
reason: ✅            # Correct
```

**Manual Workflow Inputs:**
```yaml
scrape_type:          # ❌ Should be 'incremental' boolean
  type: choice
notify:               # ❌ Should be 'announce'
create_release: ✅    # Correct
force: ✅             # Correct
reason: ✅            # Correct
```

**Issues:**
- Input name `scrape_type` doesn't match spec (should be `incremental`)
- Manual workflow uses `notify` instead of `announce`

**Status:** ⚠️ PARTIAL - 60% compliance

---

### 4. Error Handling ✅ PASSED

**Requirement:** Workflow fails if scrape exits non-zero, errors visible

**Implementation (monthly-scrape.yml:226-232):**
```yaml
# Check exit code
SCRAPE_EXIT_CODE=${PIPESTATUS[0]}
echo "Scraper exit code: $SCRAPE_EXIT_CODE"

if [[ $SCRAPE_EXIT_CODE -ne 0 ]]; then
  echo "::error::Scraper failed with exit code $SCRAPE_EXIT_CODE"
  exit $SCRAPE_EXIT_CODE
fi
```

**Implementation (manual-scrape.yml:141-145):**
```yaml
EXIT_CODE=${PIPESTATUS[0]}
if [[ $EXIT_CODE -ne 0 ]]; then
  echo "::error::Scraper failed with exit code $EXIT_CODE"
  exit $EXIT_CODE
fi
```

**Analysis:**
- Exit code properly captured using PIPESTATUS
- Non-zero exit causes workflow failure
- Error annotation visible in GitHub UI
- Log output streamed with `tee`

**Status:** ✅ PASSED

---

### 5. Statistics Generation ✅ PASSED

**Requirement:** Runs after successful scrape, handles empty database gracefully

**Implementation (monthly-scrape.yml:251-257):**
```yaml
- name: Generate statistics and release notes
  id: stats
  run: |
    bash scripts/generate-stats.sh data/irowiki.db > release-notes.md
```

**Implementation (manual-scrape.yml:163-166):**
```yaml
- name: Generate statistics
  if: github.event.inputs.create_release == 'true'
  run: |
    bash scripts/generate-stats.sh data/irowiki.db > release-notes.md || echo "Statistics generation not available"
```

**Analysis:**
- Script `scripts/generate-stats.sh` exists and is well-implemented
- Checks database exists (line 9-12 of script)
- Exits with error if database not found
- Manual workflow has fallback with `|| echo`
- Monthly workflow will fail if database empty (correct behavior)

**Status:** ✅ PASSED

---

## CLI vs Workflow Command Comparison

### What the CLI Actually Provides

```bash
$ python -m scraper --help
usage: scraper [-h] [--config CONFIG] [--database DATABASE]
               [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--quiet]
               {full,incremental} ...

Available commands:
  full                Perform a full scrape of the wiki
  incremental         Perform an incremental update
```

**Full scrape command:**
```bash
python -m scraper full [--namespace NS ...] [--rate-limit RATE] [--force] [--dry-run]
```

**Incremental scrape command:**
```bash
python -m scraper incremental [--since TIMESTAMP] [--namespace NS ...] [--rate-limit RATE]
```

### What the Workflows Try to Use

**Monthly Workflow:**
```bash
python -m scraper scrape --config config.yaml --database data/irowiki.db --log-level INFO --incremental
```
❌ No `scrape` subcommand  
❌ No `--incremental` flag

**Manual Workflow:**
```bash
python -m scraper scrape --config config.yaml --force-full
```
❌ No `scrape` subcommand  
❌ No `--force-full` flag

---

## Integration Issues

### Issue 1: Command Structure
- **User Story:** `python -m scraper incremental`
- **CLI:** `python -m scraper incremental` ✅
- **Workflows:** `python -m scraper scrape --incremental` ❌

### Issue 2: Global Flags
- **CLI:** `--config`, `--database`, `--log-level` are global flags (before subcommand)
- **Workflows:** Place flags correctly
- **Status:** ✅ Correct (but subcommand is wrong)

### Issue 3: Force Flag
- **CLI full command:** Has `--force` flag ✅
- **CLI incremental command:** No `--force` flag ❌
- **Workflows:** Try to use `--force-full` flag ❌
- **User Story:** Says `--force` should work ⚠️

### Issue 4: Workflow Input Design
- **User Story:** Boolean `incremental` input (true/false)
- **Workflows:** Choice `scrape_type` input (incremental/full)
- **Better Design:** Choice is actually more intuitive, but doesn't match spec

---

## Fixes Required

### Fix 1: Update Monthly Workflow Commands

**File:** `.github/workflows/monthly-scrape.yml`  
**Lines:** 202-232

**Replace:**
```yaml
- name: Run incremental scrape
  id: scrape
  run: |
    # Build scraper command
    SCRAPER_CMD="python -m scraper scrape"
    SCRAPER_CMD="$SCRAPER_CMD --config config.yaml"
    SCRAPER_CMD="$SCRAPER_CMD --database data/irowiki.db"
    SCRAPER_CMD="$SCRAPER_CMD --log-level INFO"
    
    if [[ "${{ steps.scrape-params.outputs.scrape_type }}" == "full" ]]; then
      SCRAPER_CMD="$SCRAPER_CMD --force-full"
    else
      SCRAPER_CMD="$SCRAPER_CMD --incremental"
    fi
    
    if [[ "${{ steps.scrape-params.outputs.force }}" == "true" ]]; then
      SCRAPER_CMD="$SCRAPER_CMD --force"
    fi
    
    # Run scraper with output streaming
    echo "Executing: $SCRAPER_CMD"
    $SCRAPER_CMD 2>&1 | tee logs/scrape.log
```

**With:**
```yaml
- name: Run scrape
  id: scrape
  run: |
    # Determine command based on scrape type
    if [[ "${{ steps.scrape-params.outputs.scrape_type }}" == "full" ]]; then
      if [[ "${{ steps.scrape-params.outputs.force }}" == "true" ]]; then
        SCRAPER_CMD="python -m scraper full --force"
      else
        SCRAPER_CMD="python -m scraper full"
      fi
    else
      SCRAPER_CMD="python -m scraper incremental"
    fi
    
    # Add global options
    SCRAPER_CMD="$SCRAPER_CMD --config config.yaml"
    SCRAPER_CMD="$SCRAPER_CMD --database data/irowiki.db"
    SCRAPER_CMD="$SCRAPER_CMD --log-level INFO"
    
    # Run scraper with output streaming
    echo "Executing: $SCRAPER_CMD"
    $SCRAPER_CMD 2>&1 | tee logs/scrape.log
    
    # Check exit code
    SCRAPE_EXIT_CODE=${PIPESTATUS[0]}
    echo "Scraper exit code: $SCRAPE_EXIT_CODE"
    
    if [[ $SCRAPE_EXIT_CODE -ne 0 ]]; then
      echo "::error::Scraper failed with exit code $SCRAPE_EXIT_CODE"
      exit $SCRAPE_EXIT_CODE
    fi
    
    echo "✓ Scrape completed successfully"
  env:
    PYTHONUNBUFFERED: "1"
```

---

### Fix 2: Update Manual Workflow Commands

**File:** `.github/workflows/manual-scrape.yml`  
**Lines:** 123-149

**Replace:**
```yaml
- name: Run scraper
  id: scrape
  run: |
    CMD="python -m scraper scrape --config config.yaml"
    
    if [[ "${{ github.event.inputs.scrape_type }}" == "full" ]]; then
      CMD="$CMD --force-full"
    else
      CMD="$CMD --incremental"
    fi
    
    if [[ "${{ github.event.inputs.force }}" == "true" ]]; then
      CMD="$CMD --force"
    fi
    
    echo "Running: $CMD"
    $CMD 2>&1 | tee logs/scrape.log
```

**With:**
```yaml
- name: Run scraper
  id: scrape
  run: |
    # Determine command based on scrape type
    if [[ "${{ github.event.inputs.scrape_type }}" == "full" ]]; then
      if [[ "${{ github.event.inputs.force }}" == "true" ]]; then
        CMD="python -m scraper full --force"
      else
        CMD="python -m scraper full"
      fi
    else
      CMD="python -m scraper incremental"
    fi
    
    # Add global options
    CMD="$CMD --config config.yaml"
    CMD="$CMD --database data/irowiki.db"
    CMD="$CMD --log-level INFO"
    
    echo "Running: $CMD"
    $CMD 2>&1 | tee logs/scrape.log
    
    EXIT_CODE=${PIPESTATUS[0]}
    if [[ $EXIT_CODE -ne 0 ]]; then
      echo "::error::Scraper failed with exit code $EXIT_CODE"
      exit $EXIT_CODE
    fi
    
    echo "✓ Scrape completed successfully"
  env:
    PYTHONUNBUFFERED: "1"
```

---

### Fix 3: Align Workflow Inputs with User Story

**DECISION NEEDED:** The user story specifies a boolean `incremental` input, but the workflows use a choice `scrape_type` input. The choice approach is actually more intuitive for users.

**Options:**

#### Option A: Match User Story Exactly (Boolean Input)
Change workflows to use boolean `incremental` input as specified.

**Pros:** Matches spec exactly  
**Cons:** Less intuitive UI (user sees true/false instead of incremental/full)

#### Option B: Keep Choice Input (Current Design)
Keep `scrape_type` choice input but acknowledge deviation from spec.

**Pros:** Better UX, clearer for maintainers  
**Cons:** Doesn't match user story letter

#### Option C: Update User Story
Update user story to reflect the better choice-based design.

**Pros:** Matches implementation, documents better pattern  
**Cons:** Changes requirements after implementation

**RECOMMENDATION:** Option B - Keep the choice input. It's a better design that's more user-friendly. Document as acceptable deviation.

---

### Fix 4: Rename `notify` to `announce` in Manual Workflow

**File:** `.github/workflows/manual-scrape.yml`  
**Line:** 30-34

**Change:**
```yaml
notify:  # ❌
  description: 'Send notifications on completion/failure'
  required: false
  default: false
  type: boolean
```

**To:**
```yaml
announce:  # ✅
  description: 'Send notifications on completion/failure'
  required: false
  default: false
  type: boolean
```

**Also update references:**
- Line 60: `echo "Notify: ${{ github.event.inputs.notify }}"`
- Line 212: `if: success() && github.event.inputs.notify == 'true'`
- Line 252: `if: failure() && github.event.inputs.notify == 'true'`

---

## Edge Cases Validation

### ✅ Full Scrape Mode
**Test:** Workflow triggers with `scrape_type=full`  
**Expected:** Uses `python -m scraper full`  
**Actual:** ❌ Uses `python -m scraper scrape --force-full`  
**Status:** WILL FAIL

### ✅ Incremental Scrape Mode
**Test:** Workflow triggers with `scrape_type=incremental`  
**Expected:** Uses `python -m scraper incremental`  
**Actual:** ❌ Uses `python -m scraper scrape --incremental`  
**Status:** WILL FAIL

### ✅ Force Flag Enabled
**Test:** Full scrape with `force=true`  
**Expected:** Uses `python -m scraper full --force`  
**Actual:** ❌ Uses `python -m scraper scrape --force-full --force`  
**Status:** WILL FAIL

### ✅ Statistics with Empty Database
**Test:** Run stats script on empty database  
**Script:** `bash scripts/generate-stats.sh empty.db`  
**Result:** Will show 0 for all counts (graceful)  
**Status:** ✅ HANDLES CORRECTLY

### ✅ Statistics with Non-Existent Database
**Test:** Run stats script on missing database  
**Script:** `bash scripts/generate-stats.sh missing.db`  
**Result:** Exits with error "Database not found"  
**Status:** ✅ FAILS CORRECTLY

### ✅ Scrape Failure Handling
**Test:** CLI exits with code 1  
**Expected:** Workflow fails, shows error  
**Implementation:** Captures PIPESTATUS, calls `exit $EXIT_CODE`  
**Status:** ✅ HANDLES CORRECTLY

---

## Summary

### Overall Status: ❌ FAILED (40% Complete)

| Criterion | Status | Notes |
|-----------|--------|-------|
| 1. Monthly Scrape Workflow | ❌ FAILED | Wrong commands, non-existent flags |
| 2. Manual Scrape Workflow | ❌ FAILED | Wrong commands, non-existent flags |
| 3. Workflow Inputs | ⚠️ PARTIAL | Wrong input names, but better UX |
| 4. Error Handling | ✅ PASSED | Correct implementation |
| 5. Statistics Generation | ✅ PASSED | Correct implementation |

### Critical Issues (Blockers)
1. Workflows use non-existent `scrape` subcommand
2. Workflows use non-existent `--force-full` and `--incremental` flags
3. Workflows will fail immediately when triggered

### Minor Issues (Non-Blockers)
1. Input name `scrape_type` instead of boolean `incremental` (better UX though)
2. Manual workflow uses `notify` instead of `announce`

---

## Recommendations

### Immediate Actions (Required)
1. ✅ Fix monthly workflow command structure
2. ✅ Fix manual workflow command structure
3. ✅ Rename `notify` to `announce` in manual workflow

### Design Decisions (Recommended)
1. ⚠️ Keep `scrape_type` choice input (better UX than boolean)
2. ⚠️ Update user story to reflect choice-based design
3. ✅ Add CLI flag `--force` to incremental command (future enhancement)

### Documentation Updates (Required)
1. Update README with correct workflow trigger examples
2. Document workflow input parameters
3. Add troubleshooting guide for workflow failures

---

## Validation Checklist

- [ ] Fix monthly workflow commands
- [ ] Fix manual workflow commands  
- [ ] Rename notify → announce
- [ ] Test monthly workflow (dry run)
- [ ] Test manual workflow with incremental=true
- [ ] Test manual workflow with scrape_type=full
- [ ] Test manual workflow with force=true
- [ ] Test workflow failure handling
- [ ] Test statistics generation
- [ ] Update documentation
- [ ] Update user story acceptance criteria

---

**Validator:** OpenCode AI  
**Validation Date:** 2026-01-24  
**Next Review:** After fixes applied
