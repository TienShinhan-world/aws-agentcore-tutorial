# Tests Documentation

Comprehensive test suite for AWS AgentCore ServiceNow webhook integration.

## Overview

This test suite ensures the robustness and reliability of the ServiceNow webhook integration with AWS AgentCore. It includes unit tests, integration tests, and end-to-end workflow tests.

## Test Structure

```
tests/
├── conftest.py                      # Common fixtures and test configuration
├── requirements-test.txt            # Test dependencies
├── test_servicenow_config.py        # Configuration tests
├── test_servicenow_client.py        # ServiceNow API client tests
├── test_webhook_handler.py          # Lambda webhook handler tests
├── test_agent_tools.py              # Agent tools tests
├── fixtures/
│   ├── sample_tickets.json          # Test ticket data
│   └── sample_responses.json        # Mock API responses
└── integration/
    └── test_webhook_flow.py         # End-to-end integration tests
```

## Installation

### Install Test Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate

# Install test dependencies
pip install -r tests/requirements-test.txt
```

### Test Dependencies

- `pytest` - Test framework
- `pytest-cov` - Code coverage
- `pytest-mock` - Mocking utilities
- `requests-mock` - HTTP mocking
- `moto` - AWS service mocking
- `freezegun` - Time mocking
- `faker` - Test data generation

## Running Tests

### Quick Start

```bash
# Run all tests with coverage
./scripts/run_tests.sh

# Or use pytest directly
pytest
```

### Run Specific Test Types

```bash
# Unit tests only
./scripts/run_tests.sh --type unit
# OR
pytest -m unit

# Integration tests only
./scripts/run_tests.sh --type integration
# OR
pytest -m integration

# Tests for specific component
pytest -m servicenow      # ServiceNow-related tests
pytest -m webhook         # Webhook tests
pytest -m agent           # Agent tool tests
```

### Run Specific Test Files

```bash
# Single test file
pytest tests/test_servicenow_config.py

# Single test class
pytest tests/test_servicenow_client.py::TestServiceNowClient

# Single test function
pytest tests/test_webhook_handler.py::TestWebhookHandler::test_parse_servicenow_payload_with_record
```

### Run Tests with Keywords

```bash
# Tests matching keyword
pytest -k webhook
pytest -k "servicenow and not integration"
pytest -k "test_update"
```

### Test Options

```bash
# Verbose output
./scripts/run_tests.sh --verbose
pytest -vv

# Stop on first failure
./scripts/run_tests.sh --failfast
pytest -x

# Show local variables in tracebacks
pytest -l

# Run tests in parallel (requires pytest-xdist)
./scripts/run_tests.sh --parallel
pytest -n auto
```

## Coverage Reports

### Generate Coverage

```bash
# Run tests with coverage (default)
./scripts/run_tests.sh

# View HTML coverage report
python -m http.server 8000 --directory htmlcov
# Then open: http://localhost:8000
```

### Coverage Reports

After running tests with coverage, you'll find:
- **HTML Report**: `htmlcov/index.html` - Interactive browser-based report
- **Terminal Report**: Displayed after test run
- **XML Report**: `coverage.xml` - For CI/CD integration

### Coverage Goals

- **Overall**: >80%
- **ServiceNow Client**: >90%
- **Configuration**: >95%
- **Webhook Handler**: >85%
- **Agent Tools**: >80%

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

Test individual components in isolation with mocked dependencies.

**Components tested:**
- ServiceNow configuration loading
- ServiceNow API client methods
- Webhook payload parsing
- Agent tool functions

**Run:**
```bash
pytest -m unit
```

### Integration Tests (`@pytest.mark.integration`)

Test multiple components working together.

**Scenarios tested:**
- Complete webhook flow (webhook → handler → agent → ServiceNow)
- Agent tools working together
- Error handling across components

**Run:**
```bash
pytest -m integration
```

### Slow Tests (`@pytest.mark.slow`)

Tests that take longer to run (e.g., performance tests, external calls).

**Skip slow tests:**
```bash
pytest -m "not slow"
```

## Writing New Tests

### Test File Naming

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test

```python
import pytest
from servicenow.client import ServiceNowClient

@pytest.mark.unit
@pytest.mark.servicenow
def test_my_feature(mock_servicenow_config):
    """Test description"""
    # Arrange
    client = ServiceNowClient(config=mock_servicenow_config)

    # Act
    result = client.some_method()

    # Assert
    assert result == expected_value
```

### Using Fixtures

Common fixtures are defined in `conftest.py`:

```python
def test_with_fixtures(
    sample_ticket_data,        # Sample ticket data
    mock_servicenow_config,    # Mock configuration
    mock_servicenow_client     # Mock client
):
    # Use fixtures in your test
    assert sample_ticket_data["number"] == "INC0001234"
```

### Markers

Available markers:
- `@pytest.mark.unit` - Unit test
- `@pytest.mark.integration` - Integration test
- `@pytest.mark.servicenow` - ServiceNow-related
- `@pytest.mark.webhook` - Webhook-related
- `@pytest.mark.agent` - Agent-related
- `@pytest.mark.slow` - Slow-running test
- `@pytest.mark.requires_aws` - Requires AWS credentials
- `@pytest.mark.requires_servicenow` - Requires ServiceNow instance

### Mocking

```python
from unittest.mock import patch, Mock

@patch('servicenow.client.requests.Session')
def test_with_mock(mock_session_class):
    # Setup mock
    mock_session = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {}}
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Test code using mock
    ...
```

## Common Test Scenarios

### Testing ServiceNow Client

```python
@patch('servicenow.client.requests.Session')
def test_client_method(mock_session_class, mock_servicenow_config):
    # Setup mock response
    mock_session = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"number": "INC0001234"}}
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Test
    client = ServiceNowClient(config=mock_servicenow_config)
    result = client.get_incident("INC0001234")

    assert result["number"] == "INC0001234"
```

### Testing Webhook Handler

```python
@patch('servicenow.webhook_handler.invoke_agent')
def test_webhook(mock_invoke_agent, sample_ticket_data):
    mock_invoke_agent.return_value = "Agent response"

    event = {
        "body": json.dumps({"record": sample_ticket_data}),
        "isBase64Encoded": False
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 200
```

### Testing Agent Tools

```python
@patch('agent.my_agent.update_ticket_with_resolution')
def test_agent_tool(mock_update):
    mock_update.return_value = {"number": "INC0001234", "state": "2"}

    result = update_servicenow_ticket("INC0001234", "Resolution notes")
    parsed = json.loads(result)

    assert parsed["success"] is True
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r tests/requirements-test.txt
      - name: Run tests
        run: ./scripts/run_tests.sh
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

## Troubleshooting

### Common Issues

**Issue: ImportError when running tests**
```bash
# Solution: Add src to Python path
export PYTHONPATH="${PYTHONPATH}:./src"
```

**Issue: Tests fail with "No module named 'servicenow'"**
```bash
# Solution: Install project in editable mode
pip install -e .
```

**Issue: Coverage not working**
```bash
# Solution: Reinstall pytest-cov
pip install --upgrade pytest-cov
```

**Issue: Mock not working as expected**
```bash
# Solution: Check mock is patching correct path
# Patch where it's used, not where it's defined
@patch('module_that_imports.ClassName')  # Correct
# Not:
@patch('module_where_defined.ClassName')  # Incorrect
```

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Clear Names**: Test names should describe what they're testing
3. **AAA Pattern**: Arrange, Act, Assert structure
4. **Mock External Calls**: Mock all HTTP requests and AWS calls
5. **Test Edge Cases**: Test error conditions, empty inputs, Unicode, etc.
6. **Use Fixtures**: Reuse common test data via fixtures
7. **Document Tests**: Add docstrings explaining what tests verify
8. **Keep Tests Fast**: Use mocks to avoid slow external calls
9. **Test One Thing**: Each test should verify one specific behavior
10. **Maintain Tests**: Update tests when code changes

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

## Support

For questions or issues with tests:
1. Check this documentation
2. Review existing test examples
3. Check pytest output for detailed error messages
4. Open an issue on GitHub
