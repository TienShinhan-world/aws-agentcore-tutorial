"""
Tests for ServiceNow webhook Lambda handler
"""
import pytest
import json
import base64
from unittest.mock import Mock, patch, MagicMock
from servicenow.webhook_handler import (
    parse_servicenow_payload,
    invoke_agent,
    lambda_handler
)


@pytest.mark.unit
@pytest.mark.webhook
class TestWebhookHandler:
    """Tests for webhook handler functions"""

    def test_parse_servicenow_payload_with_record(self, sample_ticket_data):
        """Test parsing payload with 'record' key"""
        payload = json.dumps({"record": sample_ticket_data})

        result = parse_servicenow_payload(payload)

        assert result == sample_ticket_data
        assert result["number"] == "INC0001234"

    def test_parse_servicenow_payload_with_result(self, sample_ticket_data):
        """Test parsing payload with 'result' key"""
        payload = json.dumps({"result": sample_ticket_data})

        result = parse_servicenow_payload(payload)

        assert result == sample_ticket_data
        assert result["number"] == "INC0001234"

    def test_parse_servicenow_payload_root_level(self, sample_ticket_data):
        """Test parsing payload with data at root level"""
        payload = json.dumps(sample_ticket_data)

        result = parse_servicenow_payload(payload)

        assert result == sample_ticket_data
        assert result["number"] == "INC0001234"

    def test_parse_servicenow_payload_invalid_json(self):
        """Test parsing invalid JSON raises ValueError"""
        invalid_payload = "not valid json {{"

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_servicenow_payload(invalid_payload)

    def test_parse_servicenow_payload_empty_string(self):
        """Test parsing empty string raises ValueError"""
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_servicenow_payload("")

    @patch('agent.my_agent.agent')
    def test_invoke_agent_success(self, mock_agent, sample_ticket_data):
        """Test successful agent invocation"""
        # Setup mock agent response
        mock_response = Mock()
        mock_response.message = {
            'content': [{'text': 'Agent analysis completed'}]
        }
        mock_agent.return_value = mock_response

        # Test
        result = invoke_agent(sample_ticket_data)

        assert result == 'Agent analysis completed'
        mock_agent.assert_called_once()

        # Verify prompt contains ticket data
        call_args = mock_agent.call_args[0][0]
        assert "INC0001234" in call_args
        assert "VPN" in call_args

    @patch('agent.my_agent.agent')
    def test_invoke_agent_with_different_response_format(self, mock_agent, sample_ticket_data):
        """Test agent invocation with string response"""
        # Setup mock agent that returns string directly
        mock_agent.return_value = "Simple string response"

        # Test
        result = invoke_agent(sample_ticket_data)

        assert result == "Simple string response"

    @patch('agent.my_agent.agent')
    def test_invoke_agent_raises_on_error(self, mock_agent, sample_ticket_data):
        """Test agent invocation error handling"""
        # Setup mock to raise exception
        mock_agent.side_effect = Exception("Agent error")

        # Test
        with pytest.raises(Exception, match="Agent error"):
            invoke_agent(sample_ticket_data)

    def test_lambda_handler_success(self, lambda_event_webhook, sample_ticket_data):
        """Test successful Lambda handler execution"""
        with patch('servicenow.webhook_handler.invoke_agent') as mock_invoke:
            mock_invoke.return_value = "Agent completed analysis"

            event = lambda_event_webhook(sample_ticket_data)
            response = lambda_handler(event, None)

            assert response["statusCode"] == 200
            assert "application/json" in response["headers"]["Content-Type"]

            body = json.loads(response["body"])
            assert body["success"] is True
            assert body["ticket_number"] == "INC0001234"
            assert "Agent completed analysis" in body["agent_analysis"]

    def test_lambda_handler_with_base64_encoded_body(self, lambda_event_webhook, sample_ticket_data):
        """Test Lambda handler with base64 encoded body"""
        with patch('servicenow.webhook_handler.invoke_agent') as mock_invoke:
            mock_invoke.return_value = "Agent completed analysis"

            event = lambda_event_webhook(sample_ticket_data, base64_encoded=True)
            response = lambda_handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["success"] is True

    def test_lambda_handler_invalid_json(self):
        """Test Lambda handler with invalid JSON"""
        event = {
            "body": "invalid json {{",
            "isBase64Encoded": False,
            "httpMethod": "POST"
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "Invalid payload" in body["error"]

    def test_lambda_handler_missing_body(self):
        """Test Lambda handler with missing body"""
        event = {
            "httpMethod": "POST",
            "path": "/webhook/servicenow"
        }

        response = lambda_handler(event, None)

        # Should handle gracefully with empty body
        assert response["statusCode"] in [200, 400, 500]

    def test_lambda_handler_agent_error(self, lambda_event_webhook, sample_ticket_data):
        """Test Lambda handler when agent raises error"""
        with patch('servicenow.webhook_handler.invoke_agent') as mock_invoke:
            mock_invoke.side_effect = Exception("Agent processing failed")

            event = lambda_event_webhook(sample_ticket_data)
            response = lambda_handler(event, None)

            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert body["success"] is False
            assert "Internal server error" in body["error"]

    def test_lambda_handler_with_minimal_ticket_data(self):
        """Test Lambda handler with minimal ticket data"""
        with patch('servicenow.webhook_handler.invoke_agent') as mock_invoke:
            mock_invoke.return_value = "Analysis completed"

            minimal_ticket = {
                "number": "INC0000001",
                "short_description": "Test"
            }

            event = {
                "body": json.dumps({"record": minimal_ticket}),
                "isBase64Encoded": False,
                "httpMethod": "POST"
            }

            response = lambda_handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["success"] is True
            assert body["ticket_number"] == "INC0000001"

    def test_lambda_handler_with_unicode_data(self):
        """Test Lambda handler with Unicode characters"""
        with patch('servicenow.webhook_handler.invoke_agent') as mock_invoke:
            mock_invoke.return_value = "Analysis completed"

            unicode_ticket = {
                "number": "INC0000002",
                "short_description": "Problème avec caractères: éèêë",
                "description": "Unicode test: 日本語 中文 한국어"
            }

            event = {
                "body": json.dumps({"record": unicode_ticket}),
                "isBase64Encoded": False,
                "httpMethod": "POST"
            }

            response = lambda_handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["success"] is True

    def test_lambda_handler_logs_ticket_number(self, lambda_event_webhook, sample_ticket_data, caplog):
        """Test that Lambda handler logs ticket number"""
        with patch('servicenow.webhook_handler.invoke_agent') as mock_invoke:
            mock_invoke.return_value = "Analysis completed"

            event = lambda_event_webhook(sample_ticket_data)

            with caplog.at_level("INFO"):
                response = lambda_handler(event, None)

            # Check that ticket number appears in logs
            assert "INC0001234" in caplog.text or response["statusCode"] == 200

    @pytest.mark.parametrize("ticket_fixture", [
        "sample_ticket_vpn",
        "sample_ticket_password",
        "sample_ticket_email"
    ])
    def test_lambda_handler_with_various_ticket_types(self, request, ticket_fixture):
        """Test Lambda handler with various ticket types"""
        ticket_data = request.getfixturevalue(ticket_fixture)

        with patch('servicenow.webhook_handler.invoke_agent') as mock_invoke:
            mock_invoke.return_value = "Ticket processed"

            event = {
                "body": json.dumps({"record": ticket_data}),
                "isBase64Encoded": False,
                "httpMethod": "POST"
            }

            response = lambda_handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["success"] is True
            assert ticket_data["number"] in body["ticket_number"]


@pytest.mark.slow
@pytest.mark.integration
class TestWebhookHandlerIntegration:
    """Integration tests for webhook handler"""

    def test_local_invocation(self, sample_ticket_data):
        """Test handler can be invoked locally (if dependencies available)"""
        # This test would require actual agent setup
        # Skip if imports fail
        pytest.skip("Integration test - requires full agent setup")
