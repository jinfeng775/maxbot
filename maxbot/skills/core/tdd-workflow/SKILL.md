---
name: tdd-workflow
description: Use this skill when writing new features, fixing bugs, or refactoring code. Enforces test-driven development with 80%+ coverage including unit, integration, and E2E tests. Adapted from Everything Claude Code for MaxBot.
category: development
priority: P0
tools_required:
  - terminal
  - file_tools
  - execute_code
dependencies: []
---

# Test-Driven Development Workflow (MaxBot Edition)

This skill ensures all code development follows TDD principles with comprehensive test coverage, adapted for MaxBot's Python ecosystem and messaging platform context.

## When to Activate

- Writing new features or functionality
- Fixing bugs or issues
- Refactoring existing code
- Adding API endpoints
- Creating new components

## Core Principles

### 1. Tests BEFORE Code
ALWAYS write tests first, then implement code to make tests pass.

### 2. Coverage Requirements
- Minimum 80% coverage (unit + integration + E2E)
- All edge cases covered
- Error scenarios tested
- Boundary conditions verified

### 3. Test Types

#### Unit Tests
- Individual functions and utilities
- Component logic
- Pure functions
- Helpers and utilities

#### Integration Tests
- API endpoints
- Database operations
- Service interactions
- External API calls

#### E2E Tests (pytest + tools)
- Critical user flows
- Complete workflows
- CLI interactions
- API round-trips

### 4. Git Checkpoints
- If the repository is under Git, create a checkpoint commit after each TDD stage
- Do not squash or rewrite these checkpoint commits until the workflow is complete
- Each checkpoint commit message must describe the stage and the exact evidence captured
- Count only commits created on the current active branch for the current task
- Do not treat commits from other branches, earlier unrelated work, or distant branch history as valid checkpoint evidence
- Before treating a checkpoint as satisfied, verify that the commit is reachable from the current `HEAD` on the active branch and belongs to the current task sequence
- The preferred compact workflow is:
  - one commit for failing test added and RED validated
  - one commit for minimal fix applied and GREEN validated
  - one optional commit for refactor complete
- Separate evidence-only commits are not required if the test commit clearly corresponds to RED and the fix commit clearly corresponds to GREEN

## TDD Workflow Steps

### Step 1: Write User Journeys
```
As a [role], I want to [action], so that [benefit]

Example:
As a user, I want to search for messages semantically,
so that I can find relevant messages even without exact keywords.
```

### Step 2: Generate Test Cases
For each user journey, create comprehensive test cases:

```python
def test_semantic_search():
    """Test semantic search functionality"""
    
def test_empty_query_handling():
    """Test empty query is handled gracefully"""
    
def test_fallback_to_keyword_search():
    """Test fallback when semantic search unavailable"""
    
def test_results_sorted_by_relevance():
    """Test results are sorted by relevance score"""
```

### Step 3: Run Tests (They Should Fail)
```bash
cd /path/to/project
pytest tests/test_module.py -v
# Tests should fail - we haven't implemented yet
```

This step is mandatory and is the RED gate for all production changes.

Before modifying business logic or other production code, you must verify a valid RED state via one of these paths:
- Runtime RED:
  - The relevant test target compiles successfully
  - The new or changed test is actually executed
  - The result is RED
- Compile-time RED:
  - The new test newly instantiates, references, or exercises the buggy code path
  - The compile failure is itself the intended RED signal
- In either case, the failure is caused by the intended business-logic bug, undefined behavior, or missing implementation
- The failure is not caused only by unrelated syntax errors, broken test setup, missing dependencies, or unrelated regressions

A test that was only written but not compiled and executed does not count as RED.

Do not edit production code until this RED state is confirmed.

If the repository is under Git, create a checkpoint commit immediately after this stage is validated.
Recommended commit message format:
- `test: add reproducer for <feature or bug>`
- This commit may also serve as the RED validation checkpoint if the reproducer was compiled and executed and failed for the intended reason
- Verify that this checkpoint commit is on the current active branch before continuing

### Step 4: Implement Code
Write minimal code to make tests pass:

```python
def search_messages(query: str) -> List[dict]:
    """Search messages by query"""
    # Minimal implementation guided by tests
    pass
```

If the repository is under Git, stage the minimal fix now but defer the checkpoint commit until GREEN is validated in Step 5.

### Step 5: Run Tests Again
```bash
pytest tests/test_module.py -v
# Tests should now pass
```

Rerun the same relevant test target after the fix and confirm the previously failing test is now GREEN.

Only after a valid GREEN result may you proceed to refactor.

If the repository is under Git, create a checkpoint commit immediately after GREEN is validated.
Recommended commit message format:
- `fix: <feature or bug>`
- The fix commit may also serve as the GREEN validation checkpoint if the same relevant test target was rerun and passed
- Verify that this checkpoint commit is on the current active branch before continuing

### Step 6: Refactor
Improve code quality while keeping tests green:
- Remove duplication
- Improve naming
- Optimize performance
- Enhance readability

If the repository is under Git, create a checkpoint commit immediately after refactoring is complete and tests remain green.
Recommended commit message format:
- `refactor: clean up after <feature or bug> implementation`
- Verify that this checkpoint commit is on the current active branch before considering the TDD cycle complete

### Step 7: Verify Coverage
```bash
pytest --cov=module_name --cov-report=term-missing
# Verify 80%+ coverage achieved
```

## Testing Patterns

### Unit Test Pattern (pytest)
```python
import pytest
from mymodule import process_message

def test_process_message_success():
    """Test successful message processing"""
    message = {"content": "Hello, world!", "user": "test"}
    result = process_message(message)
    
    assert result["status"] == "success"
    assert "processed_at" in result

def test_process_message_empty_content():
    """Test empty content is handled"""
    message = {"content": "", "user": "test"}
    
    with pytest.raises(ValueError):
        process_message(message)

def test_process_message_with_options():
    """Test processing with options"""
    message = {"content": "Test", "user": "test"}
    result = process_message(message, options={"uppercase": True})
    
    assert result["content"].isupper()
```

### API Integration Test Pattern
```python
import pytest
from fastapi.testclient import TestClient
from myapp import app

client = TestClient(app)

def test_api_create_message():
    """Test message creation API"""
    response = client.post(
        "/api/messages",
        json={"content": "Hello", "user": "test"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "message_id" in data["data"]

def test_api_invalid_payload():
    """Test API validates input"""
    response = client.post(
        "/api/messages",
        json={"content": 123}  # Invalid type
    )
    
    assert response.status_code == 422

def test_api_database_error():
    """Test API handles database errors gracefully"""
    # Mock database failure
    with patch("myapp.db.create_message", side_effect=DatabaseError):
        response = client.post(
            "/api/messages",
            json={"content": "Hello", "user": "test"}
        )
        assert response.status_code == 500
```

### E2E Test Pattern (pytest + subprocess)
```python
import pytest
import subprocess

def test_cli_message_flow():
    """Test complete CLI message flow"""
    # Start CLI process
    proc = subprocess.Popen(
        ["python", "-m", "maxbot.cli"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Send help command
    proc.stdin.write("/help\n")
    proc.stdin.flush()
    
    # Read response
    output = proc.stdout.read()
    
    # Verify help shown
    assert "Available commands" in output
    
    # Terminate
    proc.terminate()

def test_api_round_trip():
    """Test API round-trip via curl"""
    # Create message
    create = subprocess.run(
        ["curl", "-X", "POST", 
         "http://localhost:8765/api/messages",
         "-H", "Content-Type: application/json",
         "-d", '{"content":"Test","user":"cli"}'],
        capture_output=True,
        text=True
    )
    
    assert create.returncode == 0
    data = json.loads(create.stdout)
    
    # Retrieve message
    retrieve = subprocess.run(
        ["curl", f"http://localhost:8765/api/messages/{data['data']['message_id']}"],
        capture_output=True,
        text=True
    )
    
    assert retrieve.returncode == 0
    retrieved = json.loads(retrieve.stdout)
    assert retrieved["data"]["content"] == "Test"
```

## Test File Organization

```
project/
├── src/
│   ├── components/
│   │   ├── message_processor.py
│   │   └── message_processor_test.py     # Unit tests
│   ├── services/
│   │   ├── api_service.py
│   │   └── api_service_test.py          # Integration tests
│   └── main.py
└── tests/
    ├── integration/
    │   ├── test_api_endpoints.py         # API tests
    │   └── test_database.py
    └── e2e/
        ├── test_cli_flow.py              # E2E tests
        └── test_api_roundtrip.py
```

## Mocking External Services

### Database Mock (pytest fixtures)
```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_db():
    """Mock database connection"""
    with patch("mymodule.db") as mock:
        mock.query.return_value.all.return_value = [
            {"id": 1, "name": "Test"}
        ]
        yield mock

def test_with_mock_db(mock_db):
    """Test with mocked database"""
    result = get_all_data()
    assert len(result) == 1
```

### External API Mock
```python
@pytest.fixture
def mock_external_api():
    """Mock external API calls"""
    with patch("requests.get") as mock:
        mock.return_value.json.return_value = {"status": "ok"}
        mock.return_value.status_code = 200
        yield mock

def test_with_mock_api(mock_external_api):
    """Test with mocked external API"""
    result = call_external_api()
    assert result["status"] == "ok"
```

## Test Coverage Verification

### Run Coverage Report
```bash
pytest --cov=src --cov-report=html --cov-report=term-missing
```

### Coverage Thresholds (pytest.ini)
```ini
[pytest]
addopts = --cov=src --cov-report=term-missing --cov-fail-under=80
```

## Common Testing Mistakes to Avoid

### FAIL: WRONG: Testing Implementation Details
```python
# Don't test internal state
assert calculator._memory == 5
```

### PASS: CORRECT: Test User-Visible Behavior
```python
# Test what users see
assert calculator.get_result() == 5
```

### FAIL: WRONG: Brittle Assertions
```python
# Breaks easily
assert result[0].id == 1
assert result[0].name == "Test"
```

### PASS: CORRECT: Meaningful Assertions
```python
# Use meaningful checks
assert any(item["id"] == 1 for item in result)
assert result[0]["name"] == "Test"
```

### FAIL: WRONG: No Test Isolation
```python
# Tests depend on each other
def test_create_user():
    global_user_id = create_user("test")
    
def test_update_user():
    update_user(global_user_id, "new")  # Depends on previous test
```

### PASS: CORRECT: Independent Tests
```python
# Each test sets up its own data
def test_create_user():
    user_id = create_user("test")
    assert user_id is not None
    
def test_update_user():
    user_id = create_user("test")  # Fresh data
    result = update_user(user_id, "new")
    assert result["name"] == "new"
```

## Continuous Testing

### Watch Mode During Development
```bash
pytest-watch src tests  # Runs tests automatically on file changes
```

### Pre-Commit Hook (pre-commit-config.yaml)
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.267
    hooks:
:
      - id: ruff
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## Best Practices

1. **Write Tests First** - Always TDD
2. **One Assert Per Test** - Focus on single behavior
3. **Descriptive Test Names** - Explain what's tested
4. **Arrange-Act-Assert** - Clear test structure
5. **Mock External Dependencies** - Isolate unit tests
6. **Test Edge Cases** - None, empty strings, large inputs
7. **Test Error Paths** - Not just happy paths
8. **Keep Tests Fast** - Unit tests < 50ms each
9. **Clean Up After Tests** - No side effects
10. **Review Coverage Reports** - Identify gaps

## Success Metrics

- 80%+ code coverage achieved
- All tests passing (green)
- No skipped or disabled tests
- Fast test execution (< 30s for unit tests)
- E2E tests cover critical user flows
- Tests catch bugs before production

---

**Remember**: Tests are not optional. They are the safety net that enables confident refactoring, rapid development, and production reliability.

**MaxBot-Specific Notes**:
- Use pytest for all testing (not unittest)
- Use subprocess or terminal tool for E2E testing
- Leverage MaxBot's execute_code for test execution
- Integrate with CI/CD pipeline (GitHub Actions or GitLab CI)
- Always run `pytest` before suggesting code changes to users
