# Development Setup Guide

This guide helps you set up a local development environment for OmniCompute.

## Prerequisites

- **Python**: 3.10 or higher
- **Git**: For version control
- **pip** or **conda**: For package management
- **Text Editor**: VS Code, PyCharm, or similar
- **Terminal**: bash, zsh, or similar

## Quick Start (5 minutes)

```bash
# Clone repository
git clone https://github.com/AshraHossain/omnicompute-agent.git
cd omnicompute-agent

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests to verify setup
pytest src/omnicompute/tests/ -q
```

## Full Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/AshraHossain/omnicompute-agent.git
cd omnicompute-agent
```

### 2. Create Virtual Environment

```bash
# Using venv (recommended)
python3 -m venv venv
source venv/bin/activate

# Or using conda
conda create -n omnicompute python=3.10
conda activate omnicompute
```

### 3. Install Dependencies

```bash
# Install all dependencies including dev tools
pip install -r requirements.txt

# Optional: Install dev dependencies
pip install black flake8 mypy pytest-cov
```

### 4. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.10+

# Check installed packages
pip list | grep -E "pydantic|pytest|cryptography"

# Run a quick test
pytest src/omnicompute/tests/test_telemetry_parser.py -v
```

## IDE Setup

### VS Code

**Extensions to install**:
- Python (Microsoft)
- Pylance
- Python Docstring Generator
- Error Lens

**Settings (.vscode/settings.json)**:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "black",
  "editor.defaultFormatter": "ms-python.python"
}
```

**Run tests in VS Code**:
- Install pytest extension
- Open Test Explorer (left sidebar)
- Click "Run All Tests"

### PyCharm

**Configuration**:
1. Open project
2. Set interpreter: Preferences → Project → Python Interpreter → Add Interpreter → Existing Environment → select `venv/bin/python`
3. Mark `src/` as Sources Root: Right-click `src/` → Mark Directory as → Sources Root
4. Run tests: Right-click test file → Run

## Common Tasks

### Run All Tests

```bash
# Run with output
pytest src/omnicompute/tests/ -v

# Run with coverage
pytest src/omnicompute/tests/ --cov=src/omnicompute --cov-report=term-missing

# Run specific test file
pytest src/omnicompute/tests/test_anomaly_triager.py -v

# Run specific test
pytest src/omnicompute/tests/test_anomaly_triager.py::TestZScoreDetection::test_critical_anomaly_detected -xvs
```

### Check Code Quality

```bash
# Type checking
mypy src/omnicompute --ignore-missing-imports

# Style checking
flake8 src/omnicompute --max-line-length=100

# Format with black
black src/omnicompute
```

### Generate Test Coverage Report

```bash
# Terminal HTML report
pytest src/omnicompute/tests/ --cov=src/omnicompute --cov-report=html
open htmlcov/index.html  # macOS/Linux

# Console report with missing lines
pytest src/omnicompute/tests/ --cov=src/omnicompute --cov-report=term-missing
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Write Tests First (TDD)

```bash
# Create test file
touch src/omnicompute/tests/test_your_feature.py

# Write test (should fail initially)
pytest src/omnicompute/tests/test_your_feature.py -v
```

### 3. Implement Feature

```bash
# Edit source files
# Your implementation should make tests pass

# Run tests
pytest src/omnicompute/tests/test_your_feature.py -v

# Check coverage for your file
pytest src/omnicompute/tests/test_your_feature.py --cov=src/omnicompute/your_module
```

### 4. Verify All Tests Pass

```bash
# Run full suite
pytest src/omnicompute/tests/ -v --cov=src/omnicompute

# Check for regressions
git diff src/ | grep -E "^[+-]" | head -20
```

### 5. Format and Lint

```bash
# Auto-format code
black src/omnicompute

# Check style
flake8 src/omnicompute

# Type check
mypy src/omnicompute --ignore-missing-imports
```

### 6. Commit Changes

```bash
git add src/
git commit -m "feat: add new feature description"
# or
git commit -m "fix: resolve bug description"
```

### 7. Push and Create PR

```bash
git push -u origin feature/your-feature-name
# Then create PR on GitHub
```

## Useful Commands

### Update Dependencies

```bash
# Check for outdated packages
pip list --outdated

# Update specific package
pip install --upgrade pydantic

# Update all (use caution!)
pip install --upgrade -r requirements.txt
```

### Clean Up

```bash
# Remove cached files
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete

# Remove test artifacts
rm -rf .pytest_cache htmlcov .coverage

# Clean virtual environment
deactivate && rm -rf venv
```

### Debug Tests

```bash
# Run with verbose output
pytest src/omnicompute/tests/test_file.py -xvs

# Drop into debugger on failure
pytest src/omnicompute/tests/test_file.py --pdb

# Show print statements
pytest src/omnicompute/tests/test_file.py -s

# Run only failed tests
pytest src/omnicompute/tests/ --lf
```

## Project Structure

```
omnicompute-agent/
├── src/omnicompute/          Source code
│   ├── telemetry/            Parsing & normalization
│   ├── anomaly/              Detection & triage
│   ├── response/             Decision planning
│   ├── queue/                HITL escalation
│   ├── uplink/               Bundle generation
│   ├── pipeline/             End-to-end orchestration
│   ├── tests/                Test suite (155 tests)
│   ├── config.py             Constants
│   ├── errors.py             Exceptions
│   └── __init__.py
│
├── config/                   Configuration files
│   ├── nodes.yaml            Node inventory
│   ├── playbooks/            Response playbooks
│   └── baselines.json        Baseline statistics
│
├── data/                     Sample telemetry (not in git)
├── logs/                     Output logs (not in git)
├── queue/                    HITL queue (not in git)
├── output/                   Generated bundles (not in git)
│
├── ARCHITECTURE.md           System design
├── COMPONENTS.md             Component contracts
├── TESTING.md                Test documentation
├── DEPLOYMENT.md             Deployment guide
├── CONTRIBUTING.md           Contribution guidelines
├── CODE_OF_CONDUCT.md        Community standards
├── SECURITY.md               Security policy
├── LICENSE                   MIT License
├── requirements.txt          Python dependencies
├── pytest.ini                Test configuration
└── README.md                 Project overview
```

## Key Concepts

### Test-Driven Development (TDD)

1. **Write test first** — Define expected behavior
2. **Run test** — Watch it fail (RED)
3. **Implement feature** — Write minimal code to pass test (GREEN)
4. **Refactor** — Improve code quality (REFACTOR)
5. **Verify coverage** — Ensure 80%+ test coverage

### Components

- **TelemetryParser** — Parse and normalize sensor data
- **BaselineCache** — Maintain 30-day rolling statistics
- **AnomalyTriager** — Detect 2-sigma deviations
- **ResponsePlanner** — Generate playbook-driven actions
- **HumanReviewQueue** — Escalate complex decisions
- **UplinkBundler** — Compress and encrypt for transmission
- **Orchestrator** — Chain all components end-to-end

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'omnicompute'"

**Solution**: Activate virtual environment and reinstall:
```bash
source venv/bin/activate
pip install -e .
```

### Issue: "Tests fail with import errors"

**Solution**: Ensure src/ is in PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest src/omnicompute/tests/ -v
```

### Issue: "pytest not found"

**Solution**: Reinstall dependencies:
```bash
pip install -r requirements.txt
which pytest  # Should show path to pytest
```

### Issue: "Coverage report shows 0%"

**Solution**: Run pytest with coverage explicitly:
```bash
pytest src/omnicompute/tests/ --cov=src/omnicompute --cov-report=term-missing
```

## Resources

- **ARCHITECTURE.md** — System design and philosophy
- **COMPONENTS.md** — Component contracts and interfaces
- **TESTING.md** — Test suite documentation and patterns
- **CONTRIBUTING.md** — Contribution guidelines
- **Pydantic Docs** — https://docs.pydantic.dev/v2/
- **pytest Docs** — https://docs.pytest.org/

## Getting Help

1. Check existing GitHub issues: https://github.com/AshraHossain/omnicompute-agent/issues
2. Review documentation: ARCHITECTURE.md, COMPONENTS.md, TESTING.md
3. Ask in discussions: https://github.com/AshraHossain/omnicompute-agent/discussions
4. Contact maintainer: ashrafuzzmanhossain@gmail.com

Happy coding! 🚀
