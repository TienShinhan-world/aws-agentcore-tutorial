"""
Tests for ServiceNow API client
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import requests
from servicenow.client import (
    ServiceNowClient,
    ServiceNowError,
    update_ticket_with_resolution
)


@pytest.mark.unit
@pytest.mark.servicenow
class TestServiceNowClient:
    """Tests for ServiceNowClient class"""

    def test_client_initialization_basic_auth(self, mock_servicenow_config):
        """Test client initialization with basic auth"""
        client = ServiceNowClient(config=mock_servicenow_config)

        assert client.config == mock_servicenow_config
        assert client.session is not None
        assert client.session.auth is not None

    def test_client_initialization_oauth(self):
        """Test client initialization with OAuth"""
        from servicenow.config import ServiceNowConfig

        config = ServiceNowConfig(
            instance_url="https://test.service-now.com",
            oauth_token="test_token"
        )

        client = ServiceNowClient(config=config)

        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == "Bearer test_token"

    def test_client_initialization_no_auth_raises_error(self):
        """Test that missing auth raises ServiceNowError"""
        from servicenow.config import ServiceNowConfig

        config = ServiceNowConfig(
            instance_url="https://test.service-now.com"
        )

        with pytest.raises(ServiceNowError, match="No authentication method"):
            ServiceNowClient(config=config)

    @patch('servicenow.client.requests.Session')
    def test_get_incident_success(self, mock_session_class, mock_servicenow_config, servicenow_api_response_incident):
        """Test successful incident retrieval"""
        # Setup mock
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = servicenow_api_response_incident
        mock_response.raise_for_status = Mock()
        mock_response.content = json.dumps(servicenow_api_response_incident).encode()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        # Test
        result = client.get_incident("INC0001234")

        assert result["number"] == "INC0001234"
        assert result["sys_id"] == "abc123def456"
        mock_session.request.assert_called_once()

    @patch('servicenow.client.requests.Session')
    def test_get_incident_not_found(self, mock_session_class, mock_servicenow_config):
        """Test incident not found raises error"""
        # Setup mock
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = Mock()
        mock_response.content = b'{"result": []}'
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        # Test
        with pytest.raises(ServiceNowError, match="not found"):
            client.get_incident("INC9999999")

    @patch('servicenow.client.requests.Session')
    def test_update_incident_success(self, mock_session_class, mock_servicenow_config, servicenow_api_response_incident, servicenow_api_response_update):
        """Test successful incident update"""
        # Setup mock for both GET and PATCH
        mock_session = MagicMock()

        # First call: GET incident (to get sys_id)
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = servicenow_api_response_incident
        mock_get_response.raise_for_status = Mock()
        mock_get_response.content = json.dumps(servicenow_api_response_incident).encode()

        # Second call: PATCH update
        mock_patch_response = Mock()
        mock_patch_response.status_code = 200
        mock_patch_response.json.return_value = servicenow_api_response_update
        mock_patch_response.raise_for_status = Mock()
        mock_patch_response.content = json.dumps(servicenow_api_response_update).encode()

        mock_session.request.side_effect = [mock_get_response, mock_patch_response]
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        # Test
        result = client.update_incident("INC0001234", {"work_notes": "Test update"})

        assert result["state"] == "2"
        assert mock_session.request.call_count == 2

    @patch('servicenow.client.requests.Session')
    def test_add_work_notes(self, mock_session_class, mock_servicenow_config, servicenow_api_response_incident, servicenow_api_response_update):
        """Test adding work notes to incident"""
        # Setup mock
        mock_session = MagicMock()
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = servicenow_api_response_incident
        mock_get_response.raise_for_status = Mock()
        mock_get_response.content = json.dumps(servicenow_api_response_incident).encode()

        mock_patch_response = Mock()
        mock_patch_response.status_code = 200
        mock_patch_response.json.return_value = servicenow_api_response_update
        mock_patch_response.raise_for_status = Mock()
        mock_patch_response.content = json.dumps(servicenow_api_response_update).encode()

        mock_session.request.side_effect = [mock_get_response, mock_patch_response]
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        # Test
        result = client.add_work_notes("INC0001234", "Agent completed analysis", state="2")

        assert result["state"] == "2"

    @patch('servicenow.client.requests.Session')
    def test_resolve_incident(self, mock_session_class, mock_servicenow_config, servicenow_api_response_incident, servicenow_api_response_update):
        """Test resolving an incident"""
        # Setup mock
        mock_session = MagicMock()
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = servicenow_api_response_incident
        mock_get_response.raise_for_status = Mock()
        mock_get_response.content = json.dumps(servicenow_api_response_incident).encode()

        mock_patch_response = Mock()
        resolved_response = servicenow_api_response_update.copy()
        resolved_response["result"]["state"] = "6"
        mock_patch_response.status_code = 200
        mock_patch_response.json.return_value = resolved_response
        mock_patch_response.raise_for_status = Mock()
        mock_patch_response.content = json.dumps(resolved_response).encode()

        mock_session.request.side_effect = [mock_get_response, mock_patch_response]
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        # Test
        result = client.resolve_incident("INC0001234", "Issue resolved by agent")

        assert result["state"] == "6"

    @patch('servicenow.client.requests.Session')
    def test_set_incident_in_progress(self, mock_session_class, mock_servicenow_config, servicenow_api_response_incident, servicenow_api_response_update):
        """Test setting incident to in progress"""
        # Setup mock
        mock_session = MagicMock()
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = servicenow_api_response_incident
        mock_get_response.raise_for_status = Mock()
        mock_get_response.content = json.dumps(servicenow_api_response_incident).encode()

        mock_patch_response = Mock()
        mock_patch_response.status_code = 200
        mock_patch_response.json.return_value = servicenow_api_response_update
        mock_patch_response.raise_for_status = Mock()
        mock_patch_response.content = json.dumps(servicenow_api_response_update).encode()

        mock_session.request.side_effect = [mock_get_response, mock_patch_response]
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        # Test
        result = client.set_incident_in_progress("INC0001234", "Agent is analyzing ticket")

        assert result["state"] == "2"

    @patch('servicenow.client.requests.Session')
    def test_http_error_401(self, mock_session_class, mock_servicenow_config):
        """Test handling of 401 Unauthorized error"""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        mock_response.json.return_value = {"error": {"message": "Unauthorized"}}
        mock_response.text = "Unauthorized"
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        with pytest.raises(ServiceNowError, match="HTTP error"):
            client.get_incident("INC0001234")

    @patch('servicenow.client.requests.Session')
    def test_http_error_500(self, mock_session_class, mock_servicenow_config):
        """Test handling of 500 Server Error"""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_response.json.return_value = {"error": {"message": "Internal Server Error"}}
        mock_response.text = "Internal Server Error"
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        with pytest.raises(ServiceNowError, match="HTTP error"):
            client.get_incident("INC0001234")

    @patch('servicenow.client.requests.Session')
    def test_request_timeout(self, mock_session_class, mock_servicenow_config):
        """Test handling of request timeout"""
        mock_session = MagicMock()
        mock_session.request.side_effect = requests.exceptions.Timeout("Request timeout")
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        with pytest.raises(ServiceNowError, match="request error"):
            client.get_incident("INC0001234")

    @patch('servicenow.client.requests.Session')
    def test_connection_error(self, mock_session_class, mock_servicenow_config):
        """Test handling of connection error"""
        mock_session = MagicMock()
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        mock_session_class.return_value = mock_session

        client = ServiceNowClient(config=mock_servicenow_config)
        client.session = mock_session

        with pytest.raises(ServiceNowError, match="request error"):
            client.get_incident("INC0001234")

    @patch('servicenow.client.requests.Session')
    def test_context_manager(self, mock_session_class, mock_servicenow_config):
        """Test client as context manager"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        with ServiceNowClient(config=mock_servicenow_config) as client:
            assert client is not None

        # Verify close was called
        mock_session.close.assert_called_once()

    @patch('servicenow.client.ServiceNowClient')
    def test_update_ticket_with_resolution_convenience_function(self, mock_client_class):
        """Test convenience function for updating tickets"""
        mock_client = MagicMock()
        mock_client.add_work_notes.return_value = {"state": "2", "number": "INC0001234"}
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = update_ticket_with_resolution(
            "INC0001234",
            "Agent analysis completed",
            set_in_progress=True
        )

        assert result["state"] == "2"
        mock_client.add_work_notes.assert_called_once_with(
            number="INC0001234",
            work_notes="Agent analysis completed",
            state="2"
        )

    @patch('servicenow.client.ServiceNowClient')
    def test_update_ticket_without_state_change(self, mock_client_class):
        """Test convenience function without state change"""
        mock_client = MagicMock()
        mock_client.add_work_notes.return_value = {"number": "INC0001234"}
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = update_ticket_with_resolution(
            "INC0001234",
            "Agent analysis completed",
            set_in_progress=False
        )

        mock_client.add_work_notes.assert_called_once_with(
            number="INC0001234",
            work_notes="Agent analysis completed"
        )
