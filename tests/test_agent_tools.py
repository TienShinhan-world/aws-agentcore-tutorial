"""
Tests for agent tools
"""
import pytest
import json
from unittest.mock import patch, Mock, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent.my_agent import (
    parse_ticket_data,
    search_knowledge_base,
    update_servicenow_ticket
)


@pytest.mark.unit
@pytest.mark.agent
class TestParseTicketData:
    """Tests for parse_ticket_data tool"""

    def test_parse_valid_ticket_data(self, sample_ticket_data):
        """Test parsing valid ticket JSON"""
        ticket_json = json.dumps(sample_ticket_data)

        result = parse_ticket_data(ticket_json)
        parsed = json.loads(result)

        assert parsed["ticket_number"] == "INC0001234"
        assert parsed["short_description"] == "Unable to access VPN from home"
        assert parsed["priority"] == "2"
        assert parsed["requester"] == "john.doe@example.com"

    def test_parse_ticket_data_with_missing_fields(self):
        """Test parsing ticket with missing optional fields"""
        minimal_ticket = {
            "number": "INC0001000",
            "short_description": "Test"
        }
        ticket_json = json.dumps(minimal_ticket)

        result = parse_ticket_data(ticket_json)
        parsed = json.loads(result)

        assert parsed["ticket_number"] == "INC0001000"
        assert parsed["short_description"] == "Test"
        assert parsed["description"] == ""
        assert parsed["priority"] == ""

    def test_parse_ticket_data_invalid_json(self):
        """Test parsing invalid JSON returns error"""
        invalid_json = "not valid json {{"

        result = parse_ticket_data(invalid_json)
        parsed = json.loads(result)

        assert "error" in parsed
        assert "Failed to parse" in parsed["error"]

    def test_parse_ticket_data_empty_string(self):
        """Test parsing empty string returns error"""
        result = parse_ticket_data("")
        parsed = json.loads(result)

        assert "error" in parsed

    def test_parse_ticket_data_unicode(self):
        """Test parsing ticket with Unicode characters"""
        unicode_ticket = {
            "number": "INC0001111",
            "short_description": "Problème éèêë",
            "description": "Unicode: 日本語 中文"
        }
        ticket_json = json.dumps(unicode_ticket, ensure_ascii=False)

        result = parse_ticket_data(ticket_json)
        parsed = json.loads(result)

        assert parsed["ticket_number"] == "INC0001111"
        assert "Problème" in parsed["short_description"]


@pytest.mark.unit
@pytest.mark.agent
class TestSearchKnowledgeBase:
    """Tests for search_knowledge_base tool"""

    def test_search_vpn_keywords(self):
        """Test searching for VPN-related issues"""
        result = search_knowledge_base("VPN connection timeout")
        parsed = json.loads(result)

        assert "found_articles" in parsed
        assert parsed["found_articles"] > 0
        assert any("VPN" in article["title"] for article in parsed["articles"])

    def test_search_password_keywords(self):
        """Test searching for password-related issues"""
        result = search_knowledge_base("password reset")
        parsed = json.loads(result)

        assert parsed["found_articles"] > 0
        assert any("Password" in article["title"] for article in parsed["articles"])

    def test_search_email_keywords(self):
        """Test searching for email-related issues"""
        result = search_knowledge_base("email sync iPhone mobile")
        parsed = json.loads(result)

        assert parsed["found_articles"] > 0
        assert any("Email" in article["title"] or "Mobile" in article["title"]
                   for article in parsed["articles"])

    def test_search_no_results(self):
        """Test searching with no matching articles"""
        result = search_knowledge_base("extremely specific unique query xyz123")
        parsed = json.loads(result)

        assert "message" in parsed or "found_articles" in parsed
        if "found_articles" in parsed:
            assert parsed["found_articles"] == 0

    def test_search_case_insensitive(self):
        """Test that search is case insensitive"""
        result_lower = search_knowledge_base("vpn")
        result_upper = search_knowledge_base("VPN")
        result_mixed = search_knowledge_base("Vpn")

        parsed_lower = json.loads(result_lower)
        parsed_upper = json.loads(result_upper)
        parsed_mixed = json.loads(result_mixed)

        # All should find the same VPN article
        assert parsed_lower["found_articles"] == parsed_upper["found_articles"]
        assert parsed_upper["found_articles"] == parsed_mixed["found_articles"]

    def test_search_multiple_keywords(self):
        """Test searching with multiple keywords"""
        result = search_knowledge_base("email mobile sync iphone")
        parsed = json.loads(result)

        assert parsed["found_articles"] > 0
        # Should find email/mobile related article
        assert any("Email" in article["title"] or "Mobile" in article["title"]
                   for article in parsed["articles"])

    def test_search_returns_solution_steps(self):
        """Test that search results include solution steps"""
        result = search_knowledge_base("VPN")
        parsed = json.loads(result)

        if parsed.get("found_articles", 0) > 0:
            first_article = parsed["articles"][0]
            assert "solution" in first_article
            assert isinstance(first_article["solution"], list)
            assert len(first_article["solution"]) > 0

    def test_search_error_handling(self):
        """Test that search handles errors gracefully"""
        # Very long query
        long_query = "test " * 1000

        result = search_knowledge_base(long_query)
        parsed = json.loads(result)

        # Should not raise exception, should return valid JSON
        assert isinstance(parsed, dict)


@pytest.mark.unit
@pytest.mark.agent
@pytest.mark.servicenow
class TestUpdateServiceNowTicket:
    """Tests for update_servicenow_ticket tool"""

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_update_ticket_success(self, mock_update):
        """Test successful ticket update"""
        mock_update.return_value = {
            "sys_id": "abc123",
            "number": "INC0001234",
            "state": "2",
            "work_notes": "Agent analysis completed"
        }

        result = update_servicenow_ticket("INC0001234", "Agent has completed the analysis")
        parsed = json.loads(result)

        assert parsed["success"] is True
        assert parsed["ticket_number"] == "INC0001234"
        assert parsed["state"] == "In Progress"
        mock_update.assert_called_once_with(
            ticket_number="INC0001234",
            resolution_notes="Agent has completed the analysis",
            set_in_progress=True
        )

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_update_ticket_servicenow_error(self, mock_update):
        """Test ticket update with ServiceNow error"""
        from servicenow.client import ServiceNowError
        mock_update.side_effect = ServiceNowError("Connection failed")

        result = update_servicenow_ticket("INC0001234", "Analysis")
        parsed = json.loads(result)

        assert parsed["success"] is False
        assert "error" in parsed
        assert "Failed to update ServiceNow ticket" in parsed["error"]

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_update_ticket_unexpected_error(self, mock_update):
        """Test ticket update with unexpected error"""
        mock_update.side_effect = Exception("Unexpected error")

        result = update_servicenow_ticket("INC0001234", "Analysis")
        parsed = json.loads(result)

        assert parsed["success"] is False
        assert "error" in parsed
        assert "Unexpected error" in parsed["error"]

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_update_ticket_with_long_notes(self, mock_update):
        """Test ticket update with very long resolution notes"""
        mock_update.return_value = {
            "number": "INC0001234",
            "state": "2"
        }

        long_notes = "Analysis: " + ("A" * 5000)  # Very long notes

        result = update_servicenow_ticket("INC0001234", long_notes)
        parsed = json.loads(result)

        assert parsed["success"] is True
        # Should truncate in response
        assert len(parsed["work_notes_added"]) <= 103  # 100 chars + "..."

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_update_ticket_with_unicode(self, mock_update):
        """Test ticket update with Unicode characters"""
        mock_update.return_value = {
            "number": "INC0001234",
            "state": "2"
        }

        unicode_notes = "Résolution: problème résolu avec succès. 日本語テスト"

        result = update_servicenow_ticket("INC0001234", unicode_notes)
        parsed = json.loads(result)

        assert parsed["success"] is True
        mock_update.assert_called_once()

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_update_ticket_empty_notes(self, mock_update):
        """Test ticket update with empty resolution notes"""
        mock_update.return_value = {
            "number": "INC0001234",
            "state": "2"
        }

        result = update_servicenow_ticket("INC0001234", "")
        parsed = json.loads(result)

        # Should still work even with empty notes
        assert parsed["success"] is True

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_update_ticket_special_characters(self, mock_update):
        """Test ticket update with special characters"""
        mock_update.return_value = {
            "number": "INC0001234",
            "state": "2"
        }

        special_notes = "Resolution: Issue with <special> characters & symbols $ @ # % \"quotes\""

        result = update_servicenow_ticket("INC0001234", special_notes)
        parsed = json.loads(result)

        assert parsed["success"] is True


@pytest.mark.integration
@pytest.mark.agent
class TestAgentToolsIntegration:
    """Integration tests for agent tools working together"""

    def test_parse_and_search_workflow(self, sample_ticket_vpn):
        """Test workflow of parsing ticket and searching KB"""
        # Parse ticket
        ticket_json = json.dumps(sample_ticket_vpn)
        parse_result = parse_ticket_data(ticket_json)
        parsed_ticket = json.loads(parse_result)

        # Search based on ticket description
        search_query = parsed_ticket["short_description"]
        search_result = search_knowledge_base(search_query)
        search_parsed = json.loads(search_result)

        # Verify workflow
        assert parsed_ticket["ticket_number"] == sample_ticket_vpn["number"]
        assert search_parsed["found_articles"] > 0

    @patch('agent.my_agent.update_ticket_with_resolution')
    def test_full_ticket_processing_workflow(self, mock_update, sample_ticket_data):
        """Test complete workflow: parse -> search -> update"""
        mock_update.return_value = {"number": "INC0001234", "state": "2"}

        # 1. Parse ticket
        ticket_json = json.dumps(sample_ticket_data)
        parsed = parse_ticket_data(ticket_json)
        ticket_info = json.loads(parsed)

        # 2. Search KB
        search_result = search_knowledge_base(ticket_info["short_description"])
        kb_articles = json.loads(search_result)

        # 3. Update ticket
        resolution = f"Found {kb_articles.get('found_articles', 0)} relevant articles"
        update_result = update_servicenow_ticket(ticket_info["ticket_number"], resolution)
        update_info = json.loads(update_result)

        # Verify complete workflow
        assert ticket_info["ticket_number"] == "INC0001234"
        assert kb_articles["found_articles"] > 0
        assert update_info["success"] is True
