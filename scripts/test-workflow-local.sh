#!/bin/bash
# Test GitHub Actions workflows locally
# Simulates workflow environment for testing

set -e

echo "=== Local Workflow Testing ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [[ $1 -eq 0 ]]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Test 1: Validate YAML syntax
echo "Test 1: Validating YAML syntax..."
YAML_VALID=0
for file in .github/workflows/*.yml; do
    if python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
        print_status 0 "  $(basename $file)"
    else
        print_status 1 "  $(basename $file)"
        YAML_VALID=1
    fi
done

# Test 2: Check required scripts exist
echo ""
echo "Test 2: Checking required scripts..."
SCRIPTS_EXIST=0
for script in scripts/package-release.sh scripts/generate-stats.sh; do
    if [[ -f "$script" && -x "$script" ]]; then
        print_status 0 "  $script"
    else
        print_status 1 "  $script (missing or not executable)"
        SCRIPTS_EXIST=1
    fi
done

# Test 3: Test Python environment setup
echo ""
echo "Test 3: Testing Python environment..."
if python3 --version &>/dev/null; then
    print_status 0 "  Python installed: $(python3 --version)"
    
    # Test pip install simulation
    if pip3 list &>/dev/null; then
        print_status 0 "  pip available"
    else
        print_status 1 "  pip not available"
    fi
else
    print_status 1 "  Python not found"
fi

# Test 4: Test Go environment (if SDK exists)
echo ""
echo "Test 4: Testing Go environment..."
if [[ -d "sdk" ]]; then
    if go version &>/dev/null; then
        print_status 0 "  Go installed: $(go version)"
        
        cd sdk
        if go mod verify &>/dev/null; then
            print_status 0 "  Go modules valid"
        else
            print_status 1 "  Go modules invalid"
        fi
        cd ..
    else
        print_status 1 "  Go not found"
    fi
else
    echo "  ℹ️  SDK directory not found, skipping Go tests"
fi

# Test 5: Simulate scraper execution (dry run)
echo ""
echo "Test 5: Testing scraper command structure..."
if [[ -f "scraper/__main__.py" || -f "scraper/cli.py" ]]; then
    print_status 0 "  Scraper entry point found"
    
    # Test help command
    if python3 -m scraper --help &>/dev/null; then
        print_status 0 "  Scraper --help works"
    else
        print_status 1 "  Scraper --help failed"
    fi
else
    print_status 1 "  Scraper entry point not found"
fi

# Test 6: Test statistics generation (with dummy data)
echo ""
echo "Test 6: Testing statistics generation..."
if [[ -f "scripts/generate-stats.sh" ]]; then
    # Create dummy database for testing
    TEMP_DB=$(mktemp)
    sqlite3 "$TEMP_DB" <<SQL
CREATE TABLE pages (page_id INTEGER PRIMARY KEY, title TEXT, namespace INTEGER, created_at TEXT);
CREATE TABLE revisions (rev_id INTEGER PRIMARY KEY, page_id INTEGER, timestamp TEXT, user_name TEXT, comment TEXT);
CREATE TABLE files (file_id INTEGER PRIMARY KEY, file_exists INTEGER);
INSERT INTO pages VALUES (1, 'Test Page', 0, datetime('now'));
INSERT INTO revisions VALUES (1, 1, datetime('now'), 'TestUser', 'Test edit');
SQL
    
    if bash scripts/generate-stats.sh "$TEMP_DB" > /dev/null 2>&1; then
        print_status 0 "  Statistics generation works"
    else
        print_status 1 "  Statistics generation failed"
    fi
    
    rm -f "$TEMP_DB"
else
    print_status 1 "  generate-stats.sh not found"
fi

# Test 7: Test packaging script (dry run)
echo ""
echo "Test 7: Testing packaging script..."
if [[ -f "scripts/package-release.sh" ]]; then
    # Create dummy data
    mkdir -p test_data
    sqlite3 test_data/irowiki.db "CREATE TABLE test (id INTEGER);"
    
    # Test packaging
    if bash scripts/package-release.sh "test-version" > /dev/null 2>&1; then
        print_status 0 "  Packaging script works"
        
        # Verify output
        if [[ -d "releases" && $(ls releases/*.tar.gz 2>/dev/null | wc -l) -gt 0 ]]; then
            print_status 0 "  Archive created"
            
            # Verify checksums
            if [[ $(ls releases/*.sha256 2>/dev/null | wc -l) -gt 0 ]]; then
                print_status 0 "  Checksums generated"
            else
                print_status 1 "  Checksums missing"
            fi
        else
            print_status 1 "  Archive not created"
        fi
    else
        print_status 1 "  Packaging script failed"
    fi
    
    # Cleanup
    rm -rf test_data releases
else
    print_status 1 "  package-release.sh not found"
fi

# Test 8: Check GitHub Actions syntax
echo ""
echo "Test 8: Checking GitHub Actions syntax with actionlint..."
if command -v actionlint &>/dev/null; then
    if actionlint .github/workflows/*.yml 2>&1; then
        print_status 0 "  GitHub Actions syntax valid"
    else
        print_status 1 "  GitHub Actions syntax errors found"
    fi
else
    echo "  ℹ️  actionlint not installed, skipping (install: go install github.com/rhysd/actionlint/cmd/actionlint@latest)"
fi

# Test 9: Check secrets documentation
echo ""
echo "Test 9: Checking required secrets documentation..."
SECRETS_DOCUMENTED=0
REQUIRED_SECRETS=("GITHUB_TOKEN" "DISCORD_WEBHOOK_URL" "SLACK_WEBHOOK_URL" "CODECOV_TOKEN")
for secret in "${REQUIRED_SECRETS[@]}"; do
    if grep -q "$secret" .github/workflows/*.yml; then
        print_status 0 "  $secret used in workflows"
    else
        echo "  ⚠️  $secret not found in workflows"
    fi
done

# Summary
echo ""
echo "=== Summary ==="
if [[ $YAML_VALID -eq 0 && $SCRIPTS_EXIST -eq 0 ]]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Push workflows to GitHub"
    echo "2. Configure repository secrets (Settings > Secrets and variables > Actions)"
    echo "3. Test manual workflow trigger"
    echo "4. Wait for scheduled run or trigger manually"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please fix the issues above.${NC}"
    exit 1
fi
