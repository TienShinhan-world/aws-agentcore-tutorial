"""
ServiceNow integration module for AWS AgentCore.

This module provides:
- ServiceNowConfig: Configuration management via AWS Secrets Manager
- ServiceNowClient: REST API client for ServiceNow Table API
- Lambda handlers for AgentCore Gateway tool operations

Usage:
    from servicenow.config import ServiceNowConfig
    from servicenow.client import ServiceNowClient

    config = ServiceNowConfig.from_secrets_manager()
    with ServiceNowClient(config) as client:
        incident = client.get_incident("INC0001234")
        client.add_work_notes("INC0001234", "Analysis complete")
"""

from .config import ServiceNowConfig
from .client import ServiceNowClient

__all__ = ["ServiceNowConfig", "ServiceNowClient"]
