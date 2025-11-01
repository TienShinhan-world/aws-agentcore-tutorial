"""
Pytest configuration and common fixtures for AWS AgentCore ServiceNow integration tests
"""
import json
import os
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for ServiceNow configuration"""
    env_vars = {
        "SERVICENOW_INSTANCE_URL": "https://test-instance.service-now.com",
        "SERVICENOW_USERNAME": "test_user",
        "SERVICENOW_PASSWORD": "test_password",
        "SERVICENOW_API_VERSION": "v2",
        "SERVICENOW_TIMEOUT": "30",
        "SERVICENOW_VERIFY_SSL": "true"
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def mock_env_vars_oauth(monkeypatch):
    """Set up mock environment variables for ServiceNow with OAuth"""
    env_vars = {
        "SERVICENOW_INSTANCE_URL": "https://test-instance.service-now.com",
        "SERVICENOW_OAUTH_TOKEN": "test_oauth_token_12345",
        "SERVICENOW_API_VERSION": "v2"
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def sample_ticket_data():
    """Sample ServiceNow ticket data for testing"""
    return {
        "number": "INC0001234",
        "sys_id": "abc123def456",
        "short_description": "Unable to access VPN from home",
        "description": "User reports that VPN client shows Connection timeout error",
        "priority": "2",
        "state": "1",
        "caller_id": "john.doe@example.com",
        "assigned_to": "Support Team",
        "sys_created_on": "2025-10-31 10:30:00",
        "category": "Network",
        "subcategory": "VPN"
    }


@pytest.fixture
def sample_ticket_vpn():
    """Sample VPN-related ticket"""
    return {
        "number": "INC0001001",
        "sys_id": "vpn123",
        "short_description": "VPN connection timeout",
        "description": "Cannot connect to VPN from home office",
        "priority": "2",
        "state": "1",
        "caller_id": "user1@example.com",
        "assigned_to": "Network Team",
        "sys_created_on": "2025-10-31 08:00:00",
        "category": "Network",
        "subcategory": "VPN"
    }


@pytest.fixture
def sample_ticket_password():
    """Sample password reset ticket"""
    return {
        "number": "INC0001002",
        "sys_id": "pwd123",
        "short_description": "Password reset request",
        "description": "User forgot password and needs reset",
        "priority": "3",
        "state": "1",
        "caller_id": "user2@example.com",
        "assigned_to": "Support Team",
        "sys_created_on": "2025-10-31 09:00:00",
        "category": "Identity",
        "subcategory": "Password"
    }


@pytest.fixture
def sample_ticket_email():
    """Sample email sync ticket"""
    return {
        "number": "INC0001003",
        "sys_id": "email123",
        "short_description": "Email not syncing on iPhone",
        "description": "Corporate email stopped syncing on mobile device",
        "priority": "3",
        "state": "1",
        "caller_id": "user3@example.com",
        "assigned_to": "Support Team",
        "sys_created_on": "2025-10-31 10:00:00",
        "category": "Email",
        "subcategory": "Mobile"
    }


@pytest.fixture
def servicenow_api_response_incident():
    """Sample ServiceNow API response for get incident"""
    return {
        "result": [{
            "sys_id": "abc123def456",
            "number": "INC0001234",
            "short_description": "Test incident",
            "description": "Test description",
            "priority": "2",
            "state": "1",
            "caller_id": "test@example.com",
            "assigned_to": "Support Team",
            "sys_created_on": "2025-10-31 10:00:00"
        }]
    }


@pytest.fixture
def servicenow_api_response_update():
    """Sample ServiceNow API response for update"""
    return {
        "result": {
            "sys_id": "abc123def456",
            "number": "INC0001234",
            "state": "2",
            "work_notes": "Agent analysis completed"
        }
    }


@pytest.fixture
def lambda_event_webhook():
    """Sample Lambda event from API Gateway webhook"""
    def _make_event(ticket_data: Dict[str, Any], base64_encoded: bool = False):
        body = json.dumps({"record": ticket_data})
        if base64_encoded:
            import base64
            body = base64.b64encode(body.encode()).decode()

        return {
            "body": body,
            "isBase64Encoded": base64_encoded,
            "httpMethod": "POST",
            "path": "/webhook/servicenow",
            "headers": {
                "Content-Type": "application/json"
            }
        }
    return _make_event


@pytest.fixture
def mock_servicenow_config():
    """Mock ServiceNow configuration"""
    from servicenow.config import ServiceNowConfig
    return ServiceNowConfig(
        instance_url="https://test-instance.service-now.com",
        username="test_user",
        password="test_password",
        api_version="v2",
        timeout=30,
        verify_ssl=True
    )


@pytest.fixture
def mock_servicenow_client(mock_servicenow_config):
    """Mock ServiceNow client with configuration"""
    from servicenow.client import ServiceNowClient
    client = ServiceNowClient(config=mock_servicenow_config)
    return client


@pytest.fixture
def mock_requests_session(mocker):
    """Mock requests.Session for HTTP calls"""
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {}}
    mock_response.raise_for_status = Mock()
    mock_session.request.return_value = mock_response
    mock_session.get.return_value = mock_response
    mock_session.post.return_value = mock_response
    mock_session.patch.return_value = mock_response
    return mock_session


@pytest.fixture
def mock_agent_response():
    """Mock agent response"""
    class MockMessage:
        def __init__(self):
            self.message = {
                'content': [{
                    'text': 'Agent analysis: The ticket has been analyzed and updated in ServiceNow.'
                }]
            }
    return MockMessage()


@pytest.fixture(autouse=True)
def reset_servicenow_config():
    """Reset ServiceNow config singleton between tests"""
    import servicenow.config as config_module
    config_module._config = None
    yield
    config_module._config = None


@pytest.fixture
def clear_env_vars(monkeypatch):
    """Clear all ServiceNow-related environment variables"""
    env_vars_to_clear = [
        "SERVICENOW_INSTANCE_URL",
        "SERVICENOW_USERNAME",
        "SERVICENOW_PASSWORD",
        "SERVICENOW_OAUTH_TOKEN",
        "SERVICENOW_API_VERSION",
        "SERVICENOW_TIMEOUT",
        "SERVICENOW_VERIFY_SSL"
    ]
    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)
