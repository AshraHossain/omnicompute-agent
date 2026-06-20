#!/bin/bash
# OmniCompute Health Check Script
# Run this periodically to verify system health
# Usage: ./scripts/health_check.sh

set -e

echo "🏥 OmniCompute System Health Check"
echo "=================================="
echo ""

HEALTH_STATUS="HEALTHY"
WARNINGS=0
ERRORS=0

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Helper functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNINGS=$((WARNINGS + 1))
    HEALTH_STATUS="DEGRADED"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ERRORS=$((ERRORS + 1))
    HEALTH_STATUS="UNHEALTHY"
}

# 1. Python Environment
echo "1️⃣  Python Environment"
echo "---"
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version | awk '{print $2}')
    check_pass "Python installed: $PY_VERSION"
else
    check_fail "Python3 not found"
fi

if [ -d "venv" ]; then
    check_pass "Virtual environment exists"
else
    check_warn "Virtual environment not found (create with: python -m venv venv)"
fi

echo ""

# 2. Dependencies
echo "2️⃣  Dependencies"
echo "---"
if [ -f "requirements.txt" ]; then
    check_pass "requirements.txt found"

    # Check if all dependencies can be imported
    python3 -c "
import sys
import importlib
failed = []
with open('requirements.txt') as f:
    for line in f:
        pkg = line.strip().split('==')[0].split('[')[0]
        if pkg and not pkg.startswith('#'):
            try:
                # Try common import names
                module = pkg.replace('-', '_')
                importlib.import_module(module)
            except ImportError:
                failed.append(pkg)
if failed:
    print('\n'.join(failed))
    sys.exit(1)
" 2>/dev/null && check_pass "All dependencies installed" || check_warn "Some dependencies missing (run: pip install -r requirements.txt)"
else
    check_fail "requirements.txt not found"
fi

echo ""

# 3. Configuration Files
echo "3️⃣  Configuration Files"
echo "---"
if [ -f "config/nodes.yaml" ]; then
    check_pass "nodes.yaml exists"

    # Validate YAML syntax
    if python3 -c "import yaml; yaml.safe_load(open('config/nodes.yaml'))" 2>/dev/null; then
        check_pass "nodes.yaml syntax valid"

        # Check for required fields
        NODES=$(python3 -c "import yaml; f=yaml.safe_load(open('config/nodes.yaml')); print(len(f.get('satellites',[]))+len(f.get('ground_nodes',[])))")
        if [ "$NODES" -gt 0 ]; then
            check_pass "Configuration has $NODES nodes"
        else
            check_warn "No nodes configured in nodes.yaml"
        fi
    else
        check_fail "nodes.yaml has YAML syntax errors"
    fi
else
    check_warn "nodes.yaml not found (copy from nodes.yaml.example)"
fi

if [ -f "config/baselines.json" ]; then
    check_pass "baselines.json exists"

    # Check baseline freshness
    BASELINE_COUNT=$(python3 -c "import json; print(len(json.load(open('config/baselines.json'))))" 2>/dev/null || echo "0")
    if [ "$BASELINE_COUNT" -gt 0 ]; then
        check_pass "Baselines loaded for $BASELINE_COUNT nodes"

        # Check baseline age
        LATEST_UPDATE=$(python3 -c "
import json
from datetime import datetime
data = json.load(open('config/baselines.json'))
latest = max([v.get('battery_soc_percent',{}).get('updated_at','') for v in data.values()])
if latest:
    age = (datetime.now() - datetime.fromisoformat(latest.replace('Z',''))).days
    print(age)
else:
    print(999)
" 2>/dev/null || echo "999")

        if [ "$LATEST_UPDATE" -lt 7 ]; then
            check_pass "Baselines fresh ($LATEST_UPDATE days old)"
        elif [ "$LATEST_UPDATE" -lt 30 ]; then
            check_warn "Baselines aging ($LATEST_UPDATE days old, refresh recommended)"
        else
            check_fail "Baselines stale ($LATEST_UPDATE days old, update immediately)"
        fi
    else
        check_warn "Baselines empty or invalid"
    fi
else
    check_warn "baselines.json not found (use nominal values for cold start)"
fi

echo ""

# 4. Playbooks
echo "4️⃣  Playbooks"
echo "---"
if [ -d "config/playbooks" ]; then
    PLAYBOOK_COUNT=$(find config/playbooks -name "*.yaml" | wc -l)
    if [ "$PLAYBOOK_COUNT" -gt 0 ]; then
        check_pass "Found $PLAYBOOK_COUNT playbooks"

        # Validate each playbook
        INVALID=0
        for pb in config/playbooks/*.yaml; do
            if ! python3 -c "import yaml; yaml.safe_load(open('$pb'))" 2>/dev/null; then
                check_warn "Playbook syntax error: $(basename $pb)"
                INVALID=$((INVALID + 1))
            fi
        done

        if [ "$INVALID" -eq 0 ]; then
            check_pass "All playbooks have valid YAML syntax"
        fi
    else
        check_warn "No playbooks found (create from example_power_anomaly.yaml)"
    fi
else
    check_fail "config/playbooks directory not found"
fi

echo ""

# 5. Logs & Output
echo "5️⃣  Logs & Output"
echo "---"
if [ -d "logs" ]; then
    LOG_COUNT=$(find logs -name "*.jsonl" 2>/dev/null | wc -l)
    check_pass "Logs directory exists ($LOG_COUNT log files)"

    # Check for recent activity
    if [ "$LOG_COUNT" -gt 0 ]; then
        LATEST_LOG=$(find logs -name "*.jsonl" -exec ls -t {} \; 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            MTIME=$(stat -f "%m" "$LATEST_LOG" 2>/dev/null || stat -c "%Y" "$LATEST_LOG")
            NOW=$(date +%s)
            AGE_MINUTES=$(( ($NOW - $MTIME) / 60 ))

            if [ "$AGE_MINUTES" -lt 1440 ]; then
                check_pass "Recent activity detected (${AGE_MINUTES} minutes ago)"
            else
                check_warn "No activity in last 24 hours"
            fi
        fi
    fi
else
    check_warn "logs directory not found (will be created on first run)"
fi

if [ -d "output" ]; then
    BUNDLE_COUNT=$(find output -name "uplink_bundle_*.json" 2>/dev/null | wc -l)
    check_pass "Output directory exists ($BUNDLE_COUNT bundles)"
else
    check_warn "output directory not found (will be created on first run)"
fi

if [ -d "queue" ]; then
    if [ -f "queue/hitl_review.json" ]; then
        QUEUE_SIZE=$(python3 -c "import json; print(len(json.load(open('queue/hitl_review.json')).get('pending_items',[])))" 2>/dev/null || echo "?")
        check_pass "HITL queue exists ($QUEUE_SIZE pending items)"

        if [ "$QUEUE_SIZE" -gt 80 ]; then
            check_warn "HITL queue near capacity ($QUEUE_SIZE/100)"
        fi
    fi
else
    check_warn "queue directory not found (will be created on first run)"
fi

echo ""

# 6. Tests
echo "6️⃣  Tests & Coverage"
echo "---"
if [ -d "src/omnicompute/tests" ]; then
    TEST_COUNT=$(find src/omnicompute/tests -name "test_*.py" | wc -l)
    check_pass "Found $TEST_COUNT test files"

    if command -v pytest &> /dev/null; then
        # Run tests with timeout
        if timeout 60 pytest src/omnicompute/tests/ --tb=no -q 2>/dev/null; then
            check_pass "All tests passing"
        else
            check_fail "Some tests failing (run: pytest src/omnicompute/tests/ -v)"
        fi
    else
        check_warn "pytest not installed (run: pip install pytest)"
    fi
else
    check_fail "Tests directory not found"
fi

echo ""

# 7. Encryption
echo "7️⃣  Encryption"
echo "---"
if [ -n "$OMNICOMPUTE_ENCRYPTION_KEY" ]; then
    check_pass "Encryption key is set"

    # Validate key format
    if python3 -c "
from cryptography.fernet import Fernet
try:
    Fernet(b'$OMNICOMPUTE_ENCRYPTION_KEY')
    print('valid')
except:
    print('invalid')
" 2>/dev/null | grep -q "valid"; then
        check_pass "Encryption key is valid (Fernet format)"
    else
        check_fail "Encryption key is invalid (not valid Fernet key)"
    fi
else
    check_warn "Encryption key not set (OMNICOMPUTE_ENCRYPTION_KEY environment variable)"
fi

echo ""

# 8. File Permissions
echo "8️⃣  File Permissions"
echo "---"
# Check sensitive files have restricted permissions
for file in config/baselines.json queue/hitl_review.json logs/*.jsonl; do
    if [ -f "$file" ] 2>/dev/null; then
        PERMS=$(ls -l "$file" | awk '{print $1}')
        if [[ "$PERMS" == *"rw-------"* ]] || [[ "$PERMS" == *"rw-r--r--"* ]]; then
            check_pass "File permissions OK: $file"
        else
            check_warn "Restrictive permissions recommended for: $file"
        fi
    fi
done

echo ""

# 9. Disk Space
echo "9️⃣  Disk Space"
echo "---"
DISK_USAGE=$(du -sh . 2>/dev/null | awk '{print $1}')
check_pass "Project size: $DISK_USAGE"

if [ -d "archive" ]; then
    ARCHIVE_SIZE=$(du -sh archive 2>/dev/null | awk '{print $1}')
    check_pass "Archive size: $ARCHIVE_SIZE"
fi

echo ""

# 10. Dependencies Check
echo "🔟 Python Imports"
echo "---"
python3 -c "
import sys
imports = [
    ('pydantic', 'Pydantic (data validation)'),
    ('cryptography', 'Cryptography (Fernet encryption)'),
    ('yaml', 'PyYAML (configuration parsing)'),
    ('pytest', 'Pytest (testing)'),
]
for module, name in imports:
    try:
        __import__(module)
        print(f'✓ {name}')
    except ImportError:
        print(f'✗ {name} - missing')
" 2>&1 | while read line; do
    if [[ "$line" == ✓* ]]; then
        echo -e "${GREEN}${line}${NC}"
    else
        echo -e "${RED}${line}${NC}"
    fi
done

echo ""
echo "=================================="
echo "📊 Summary"
echo "---"
echo -e "Status: ${GREEN}${HEALTH_STATUS}${NC}"
echo "Warnings: $WARNINGS"
echo "Errors: $ERRORS"
echo ""

if [ "$HEALTH_STATUS" = "HEALTHY" ]; then
    echo "✅ System is healthy and ready for operation"
    exit 0
elif [ "$HEALTH_STATUS" = "DEGRADED" ]; then
    echo "⚠️  System is operational but has degraded features"
    exit 0
else
    echo "❌ System has critical issues that need attention"
    exit 1
fi
