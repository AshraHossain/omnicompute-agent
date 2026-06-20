# Contributing to OmniCompute

Thank you for your interest in contributing to the OmniCompute Federated Infrastructure Agent! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful, inclusive, and professional in all interactions.

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- pip or conda

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/AshraHossain/omnicompute-agent.git
cd omnicompute-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests to verify setup
pytest src/omnicompute/tests/ -v --cov=src/omnicompute
```

## Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Follow TDD (Test-Driven Development)

- Write tests first (RED state)
- Implement to pass tests (GREEN state)
- Refactor and improve (BLUE state)
- Ensure 80%+ test coverage

```bash
pytest src/omnicompute/tests/ --cov=src/omnicompute --cov-report=term-missing
```

### 3. Commit with Conventional Format

```bash
git commit -m "feat: add new anomaly detection method"
git commit -m "fix: handle edge case in baseline calculation"
git commit -m "test: add integration tests for pipeline"
git commit -m "docs: update COMPONENTS.md with new module"
```

**Types**: `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `chore`, `ci`

### 4. Push and Create PR

```bash
git push -u origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title (under 70 characters)
- Detailed description of changes
- Test plan and edge cases covered
- Any breaking changes noted

### 5. Await Review

- GitHub Actions will automatically run tests
- Maintain 97%+ coverage (current baseline)
- All tests must pass before merge
- Address review feedback promptly

## Code Standards

### Python Style

- Follow PEP 8
- Use type hints on all function signatures
- Keep functions small (<50 lines)
- Keep files focused (<800 lines)
- Use meaningful variable names

### Testing

- Minimum 80% test coverage (target: 97%)
- Test structure: happy path → error cases → edge cases
- Use pytest with fixtures for test data
- Parametrize tests for multiple cases

### Documentation

- Update README.md if behavior changes
- Update COMPONENTS.md if adding new modules
- Update DATA_SCHEMAS.md if changing Pydantic models
- Add inline comments only for non-obvious logic

## Architecture

The project uses a layered pipeline:

```
TelemetryParser → BaselineCache → AnomalyTriager → ResponsePlanner → 
HumanReviewQueue → UplinkBundler → Orchestrator
```

Each component is:
- Independent and testable
- Documented with clear contracts
- Validated with comprehensive tests
- Loosely coupled to others

## Project Structure

```
src/omnicompute/
├── telemetry/      Phase 1: parsing
├── anomaly/        Phase 1: detection
├── response/       Phase 2: planning
├── queue/          Phase 2: escalation
├── uplink/         Phase 3: bundling
├── pipeline/       Phase 3: orchestration
├── config.py       Constants
├── errors.py       Exceptions
└── tests/          Test suite
```

## Reporting Issues

Use GitHub Issues to report:
- **Bugs**: Title format: `[BUG] Brief description`
- **Features**: Title format: `[FEATURE] Brief description`
- **Questions**: Title format: `[QUESTION] Brief description`

Include:
- Clear description of the issue
- Steps to reproduce (for bugs)
- Expected vs. actual behavior
- Python version, OS, environment details

## Questions?

- Check existing documentation: README.md, TESTING.md, COMPONENTS.md
- Search closed issues for similar questions
- Open a discussion or issue on GitHub

## Recognition

Contributors are recognized in:
- Commit history (git log)
- GitHub contributors page
- Release notes for significant contributions

Thank you for making OmniCompute better! 🚀
