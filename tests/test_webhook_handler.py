"""
Unit tests for ServiceNow webhook handler.

Tests cover:
- Payload parsing from different ServiceNow formats
- Prompt building from incident data
- Agent invocation via Bedrock
- Error handling and response formatting
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# Import the handler module
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/webhook"))

import handler


class TestParseServiceNowPayload:
    """Tests for parse_servicenow_payload function."""

    def test_parse_direct_incident_format(self):
        """Test parsing when incident is at root level."""
        payload = {
            "number": "INC0001234",
            "short_description": "Cannot access email",
            "description": "User reports cannot access email since this morning",
            "urgency": "2",
            "impact": "2",
            "priority": "2",
            "state": "1",
            "category": "Email",
        }

        result = handler.parse_servicenow_payload(payload)

        assert result["number"] == "INC0001234"
        assert result["short_description"] == "Cannot access email"
        assert result["urgency"] == "2"
        assert result["category"] == "Email"

    def test_parse_nested_record_format(self):
        """Test parsing when incident is nested under 'record' key."""
        payload = {
            "record": {
                "number": "INC0005678",
                "short_description": "VPN connection fails",
                "description": "VPN keeps disconnecting",
                "urgency": "1",
                "impact": "1",
                "priority": "1",
            }
        }

        result = handler.parse_servicenow_payload(payload)

        assert result["number"] == "INC0005678"
        assert result["short_description"] == "VPN connection fails"
        assert result["urgency"] == "1"

    def test_parse_missing_optional_fields(self):
        """Test parsing with only required fields."""
        payload = {
            "number": "INC0009999",
            "short_description": "Test incident",
        }

        result = handler.parse_servicenow_payload(payload)

        assert result["number"] == "INC0009999"
        assert result["short_description"] == "Test incident"
        # Check defaults
        assert result["urgency"] == "3"
        assert result["priority"] == "4"
        assert result["description"] == ""

    def test_parse_missing_required_number(self):
        """Test that ValueError is raised when incident number is missing."""
        payload = {
            "short_description": "No number",
        }

        with pytest.raises(ValueError, match="Missing required field: incident number"):
            handler.parse_servicenow_payload(payload)

    def test_parse_all_fields(self):
        """Test parsing with all possible fields."""
        payload = {
            "number": "INC0001111",
            "short_description": "Complete incident",
            "description": "Full description",
            "urgency": "1",
            "impact": "1",
            "priority": "1",
            "state": "2",
            "assigned_to": "john.doe",
            "assignment_group": "IT Support",
            "category": "Hardware",
            "subcategory": "Laptop",
            "caller_id": "jane.smith",
            "sys_created_on": "2025-01-15 10:30:00",
            "sys_updated_on": "2025-01-15 11:45:00",
        }

        result = handler.parse_servicenow_payload(payload)

        assert result["number"] == "INC0001111"
        assert result["assigned_to"] == "john.doe"
        assert result["assignment_group"] == "IT Support"
        assert result["category"] == "Hardware"
        assert result["subcategory"] == "Laptop"
        assert result["caller"] == "jane.smith"


class TestBuildAgentPrompt:
    """Tests for build_agent_prompt function."""

    def test_build_prompt_with_all_fields(self):
        """Test prompt building with complete incident data."""
        incident_data = {
            "number": "INC0001234",
            "short_description": "Email issue",
            "description": "Cannot send emails",
            "urgency": "2",
            "impact": "2",
            "priority": "2",
            "category": "Email",
            "subcategory": "Outlook",
            "assignment_group": "Email Support",
        }

        prompt = handler.build_agent_prompt(incident_data)

        # Verify all key fields are in the prompt
        assert "INC0001234" in prompt
        assert "Email issue" in prompt
        assert "Cannot send emails" in prompt
        assert "Priority: 2" in prompt
        assert "Category: Email" in prompt
        assert "Subcategory: Outlook" in prompt
        assert "Assignment Group: Email Support" in prompt

    def test_build_prompt_structure(self):
        """Test that prompt has expected structure."""
        incident_data = {
            "number": "INC0001234",
            "short_description": "Test",
            "description": "Test description",
            "urgency": "3",
            "impact": "3",
            "priority": "4",
            "category": "",
            "subcategory": "",
            "assignment_group": "",
        }

        prompt = handler.build_agent_prompt(incident_data)

        # Check for expected sections
        assert "Analyze the following ServiceNow incident:" in prompt
        assert "Please analyze this incident and provide:" in prompt
        assert "summary of the issue" in prompt
        assert "root causes" in prompt
        assert "resolution steps" in prompt
        assert "knowledge base articles" in prompt


class TestInvokeAgent:
    """Tests for invoke_agent function."""

    @patch("handler.bedrock_agent_runtime")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_invoke_agent_success(self, mock_bedrock):
        """Test successful agent invocation."""
        # Mock successful response
        mock_bedrock.invoke_agent.return_value = {
            "completion": [
                {
                    "chunk": {
                        "bytes": b"This is the agent's response about the incident."
                    }
                }
            ]
        }

        prompt = "Analyze incident INC0001234"
        result = handler.invoke_agent(prompt)

        assert result == "This is the agent's response about the incident."
        mock_bedrock.invoke_agent.assert_called_once()

        # Verify call parameters
        call_args = mock_bedrock.invoke_agent.call_args[1]
        assert call_args["agentId"] == "test-agent-id"
        assert call_args["inputText"] == prompt

    @patch("handler.bedrock_agent_runtime")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_invoke_agent_with_session_id(self, mock_bedrock):
        """Test agent invocation with session ID."""
        mock_bedrock.invoke_agent.return_value = {
            "completion": [{"chunk": {"bytes": b"Response"}}]
        }

        result = handler.invoke_agent("Test prompt", session_id="test-session-123")

        call_args = mock_bedrock.invoke_agent.call_args[1]
        assert call_args["sessionId"] == "test-session-123"

    @patch.dict(os.environ, {}, clear=True)
    def test_invoke_agent_missing_agent_id(self):
        """Test that RuntimeError is raised when AGENT_ID is not set."""
        with pytest.raises(RuntimeError, match="AGENT_ID environment variable not set"):
            handler.invoke_agent("Test prompt")

    @patch("handler.bedrock_agent_runtime")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_invoke_agent_bedrock_error(self, mock_bedrock):
        """Test handling of Bedrock client errors."""
        from botocore.exceptions import ClientError

        mock_bedrock.invoke_agent.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid agent ID"}},
            "InvokeAgent",
        )

        with pytest.raises(RuntimeError, match="Failed to invoke agent"):
            handler.invoke_agent("Test prompt")

    @patch("handler.bedrock_agent_runtime")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_invoke_agent_multiple_chunks(self, mock_bedrock):
        """Test agent response with multiple chunks."""
        mock_bedrock.invoke_agent.return_value = {
            "completion": [
                {"chunk": {"bytes": b"First part. "}},
                {"chunk": {"bytes": b"Second part. "}},
                {"chunk": {"bytes": b"Third part."}},
            ]
        }

        result = handler.invoke_agent("Test")

        assert result == "First part. Second part. Third part."


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch("handler.invoke_agent")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_handler_success(self, mock_invoke):
        """Test successful webhook handling."""
        mock_invoke.return_value = "Agent analysis result"

        event = {
            "body": json.dumps({
                "number": "INC0001234",
                "short_description": "Test incident",
                "description": "Test description",
                "urgency": "2",
                "impact": "2",
                "priority": "2",
            })
        }

        response = handler.lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["incident_number"] == "INC0001234"
        assert body["analysis"] == "Agent analysis result"

    @patch("handler.invoke_agent")
    def test_handler_invalid_payload(self, mock_invoke):
        """Test handling of invalid payload."""
        event = {
            "body": json.dumps({
                "short_description": "No incident number"
            })
        }

        response = handler.lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "Invalid request payload" in body["error"]

    @patch("handler.invoke_agent")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_handler_agent_error(self, mock_invoke):
        """Test handling of agent invocation errors."""
        mock_invoke.side_effect = RuntimeError("Agent invocation failed")

        event = {
            "body": json.dumps({
                "number": "INC0001234",
                "short_description": "Test",
            })
        }

        response = handler.lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["success"] is False
        assert "Failed to invoke agent" in body["error"]

    @patch("handler.invoke_agent")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_handler_nested_record_format(self, mock_invoke):
        """Test handling of nested record format."""
        mock_invoke.return_value = "Analysis"

        event = {
            "body": json.dumps({
                "record": {
                    "number": "INC0005678",
                    "short_description": "Nested incident",
                }
            })
        }

        response = handler.lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["incident_number"] == "INC0005678"

    def test_handler_invalid_json(self):
        """Test handling of invalid JSON in request body."""
        event = {
            "body": "not valid json {"
        }

        response = handler.lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["success"] is False

    @patch("handler.invoke_agent")
    @patch.dict(os.environ, {"AGENT_ID": "test-agent-id"})
    def test_handler_session_id_from_incident_number(self, mock_invoke):
        """Test that session ID is generated from incident number."""
        mock_invoke.return_value = "Response"

        event = {
            "body": json.dumps({
                "number": "INC0001234",
                "short_description": "Test",
            })
        }

        handler.lambda_handler(event, None)

        # Verify session ID was passed to invoke_agent
        mock_invoke.assert_called_once()
        call_args = mock_invoke.call_args
        assert call_args[1]["session_id"] == "servicenow-INC0001234"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
