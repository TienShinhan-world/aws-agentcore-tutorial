"""
End-to-end integration tests for ServiceNow webhook flow

These tests verify the complete flow:
ServiceNow Webhook -> Lambda Handler -> Agent -> ServiceNow API Update
"""
import pytest
import json
from unittest.mock import patch, Mock, MagicMock
from servicenow.webhook_handler import lambda_handler


@pytest.mark.integration
@pytest.mark.webhook
class TestWebhookFlowIntegration:
    """Integration tests for complete webhook processing flow"""

    @patch('agent.my_agent.agent')
    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_complete_webhook_to_servicenow_flow(
        self,
        mock_update_ticket,
        mock_agent,
        sample_ticket_vpn
    ):
        """Test complete flow from webhook receipt to ServiceNow update"""
        # Setup mocks
        mock_agent_response = Mock()
        mock_agent_response.message = {
            'content': [{
                'text': 'Agent has analyzed the VPN issue and updated the ticket'
            }]
        }
        mock_agent.return_value = mock_agent_response

        mock_update_ticket.return_value = {
            "sys_id": "vpn123",
            "number": "INC0001001",
            "state": "2"
        }

        # Create webhook event
        event = {
            "body": json.dumps({"record": sample_ticket_vpn}),
            "isBase64Encoded": False,
            "httpMethod": "POST",
            "path": "/webhook/servicenow"
        }

        # Execute
        response = lambda_handler(event, None)

        # Verify
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["ticket_number"] == "INC0001001"

        # Verify agent was called
        mock_agent.assert_called_once()

        # Verify agent received ticket data in prompt
        agent_call_args = mock_agent.call_args[0][0]
        assert "INC0001001" in agent_call_args
        assert "VPN" in agent_call_args

    @patch('agent.my_agent.agent')
    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_webhook_flow_with_password_reset(
        self,
        mock_update_ticket,
        mock_agent,
        sample_ticket_password
    ):
        """Test flow with password reset ticket"""
        mock_agent_response = Mock()
        mock_agent_response.message = {
            'content': [{
                'text': 'Password reset procedure has been provided'
            }]
        }
        mock_agent.return_value = mock_agent_response

        mock_update_ticket.return_value = {
            "number": "INC0001002",
            "state": "2"
        }

        event = {
            "body": json.dumps({"record": sample_ticket_password}),
            "isBase64Encoded": False,
            "httpMethod": "POST"
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "INC0001002" in body["ticket_number"]

    @patch('agent.my_agent.agent')
    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_webhook_flow_with_servicenow_error(
        self,
        mock_update_ticket,
        mock_agent,
        sample_ticket_data
    ):
        """Test flow when ServiceNow update fails"""
        from servicenow.client import ServiceNowError

        # Agent succeeds but ServiceNow update fails
        mock_agent_response = Mock()
        mock_agent_response.message = {
            'content': [{'text': 'Analysis complete'}]
        }
        mock_agent.return_value = mock_agent_response

        mock_update_ticket.side_effect = ServiceNowError("Connection timeout")

        event = {
            "body": json.dumps({"record": sample_ticket_data}),
            "isBase64Encoded": False,
            "httpMethod": "POST"
        }

        # Handler should still return 200 (webhook received successfully)
        # but agent's response will indicate ServiceNow update failed
        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True

    @patch('agent.my_agent.agent')
    def test_webhook_flow_with_agent_error(self, mock_agent, sample_ticket_data):
        """Test flow when agent processing fails"""
        # Agent raises exception
        mock_agent.side_effect = Exception("Agent processing error")

        event = {
            "body": json.dumps({"record": sample_ticket_data}),
            "isBase64Encoded": False,
            "httpMethod": "POST"
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "Internal server error" in body["error"]

    @patch('agent.my_agent.agent')
    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_webhook_flow_with_multiple_kb_articles(
        self,
        mock_update_ticket,
        mock_agent,
        sample_ticket_email
    ):
        """Test flow where KB search finds multiple articles"""
        mock_agent_response = Mock()
        mock_agent_response.message = {
            'content': [{
                'text': 'Found 3 relevant articles about email sync issues. Updated ticket with solution steps.'
            }]
        }
        mock_agent.return_value = mock_agent_response

        mock_update_ticket.return_value = {
            "number": "INC0001003",
            "state": "2"
        }

        event = {
            "body": json.dumps({"record": sample_ticket_email}),
            "isBase64Encoded": False,
            "httpMethod": "POST"
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True

    @patch('agent.my_agent.agent')
    @patch('agent.my_agent.update_ticket_with_resolution')
    @pytest.mark.parametrize("encoding", [False, True])
    def test_webhook_flow_with_different_encodings(
        self,
        mock_update_ticket,
        mock_agent,
        sample_ticket_data,
        encoding
    ):
        """Test flow with base64 encoded and non-encoded payloads"""
        mock_agent_response = Mock()
        mock_agent_response.message = {
            'content': [{'text': 'Ticket processed'}]
        }
        mock_agent.return_value = mock_agent_response

        mock_update_ticket.return_value = {
            "number": "INC0001234",
            "state": "2"
        }

        body = json.dumps({"record": sample_ticket_data})
        if encoding:
            import base64
            body = base64.b64encode(body.encode()).decode()

        event = {
            "body": body,
            "isBase64Encoded": encoding,
            "httpMethod": "POST"
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body_parsed = json.loads(response["body"])
        assert body_parsed["success"] is True

    @patch('agent.my_agent.agent')
    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_webhook_flow_performance(
        self,
        mock_update_ticket,
        mock_agent,
        sample_ticket_data
    ):
        """Test that webhook flow completes in reasonable time"""
        import time

        mock_agent_response = Mock()
        mock_agent_response.message = {
            'content': [{'text': 'Quick response'}]
        }
        mock_agent.return_value = mock_agent_response

        mock_update_ticket.return_value = {"number": "INC0001234", "state": "2"}

        event = {
            "body": json.dumps({"record": sample_ticket_data}),
            "isBase64Encoded": False,
            "httpMethod": "POST"
        }

        start_time = time.time()
        response = lambda_handler(event, None)
        elapsed_time = time.time() - start_time

        assert response["statusCode"] == 200
        # Should complete in less than 5 seconds (with mocks)
        assert elapsed_time < 5.0

    @patch('agent.my_agent.agent')
    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_webhook_flow_with_unicode_ticket(
        self,
        mock_update_ticket,
        mock_agent
    ):
        """Test flow with Unicode characters in ticket"""
        unicode_ticket = {
            "number": "INC0010007",
            "sys_id": "unicode_001",
            "short_description": "Problème avec caractères spéciaux: éèêë",
            "description": "Test Unicode: 日本語 中文 한국어 العربية",
            "priority": "3",
            "state": "1"
        }

        mock_agent_response = Mock()
        mock_agent_response.message = {
            'content': [{'text': 'Unicode ticket processed successfully'}]
        }
        mock_agent.return_value = mock_agent_response

        mock_update_ticket.return_value = {"number": "INC0010007", "state": "2"}

        event = {
            "body": json.dumps({"record": unicode_ticket}, ensure_ascii=False),
            "isBase64Encoded": False,
            "httpMethod": "POST"
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True


@pytest.mark.slow
@pytest.mark.integration
class TestWebhookFlowWithRealAgent:
    """Integration tests with actual agent (requires full setup)"""

    @pytest.mark.skip(reason="Requires full agent setup with AWS credentials")
    def test_webhook_with_real_agent_invocation(self, sample_ticket_data):
        """Test webhook with actual agent invocation"""
        # This would require:
        # - AWS credentials configured
        # - Bedrock access
        # - Real ServiceNow instance
        pass

    @pytest.mark.skip(reason="Requires AWS Lambda environment")
    def test_webhook_in_lambda_environment(self, sample_ticket_data):
        """Test webhook handler in actual Lambda environment"""
        # This would be run in actual Lambda for end-to-end validation
        pass
