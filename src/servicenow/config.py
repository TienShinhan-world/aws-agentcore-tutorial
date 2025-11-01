"""
ServiceNow Configuration Module

This module manages configuration for ServiceNow API integration.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServiceNowConfig:
    """ServiceNow configuration container"""

    instance_url: str
    username: Optional[str] = None
    password: Optional[str] = None

    # Alternative: OAuth token
    oauth_token: Optional[str] = None

    # API version and settings
    api_version: str = "v2"
    timeout: int = 30
    verify_ssl: bool = True

    @classmethod
    def from_environment(cls) -> "ServiceNowConfig":
        """
        Load ServiceNow configuration from environment variables.

        Expected environment variables:
        - SERVICENOW_INSTANCE_URL: ServiceNow instance URL (e.g., https://dev12345.service-now.com)
        - SERVICENOW_USERNAME: ServiceNow username (optional if using OAuth)
        - SERVICENOW_PASSWORD: ServiceNow password (optional if using OAuth)
        - SERVICENOW_OAUTH_TOKEN: OAuth token (optional if using basic auth)
        - SERVICENOW_API_VERSION: API version (default: v2)
        - SERVICENOW_TIMEOUT: Request timeout in seconds (default: 30)
        - SERVICENOW_VERIFY_SSL: Verify SSL certificates (default: true)

        Returns:
            ServiceNowConfig: Configuration object

        Raises:
            ValueError: If required configuration is missing
        """
        instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
        if not instance_url:
            raise ValueError(
                "SERVICENOW_INSTANCE_URL environment variable is required"
            )

        # Remove trailing slash if present
        instance_url = instance_url.rstrip("/")

        username = os.getenv("SERVICENOW_USERNAME")
        password = os.getenv("SERVICENOW_PASSWORD")
        oauth_token = os.getenv("SERVICENOW_OAUTH_TOKEN")

        # Validate auth method
        if not oauth_token and not (username and password):
            raise ValueError(
                "Either SERVICENOW_OAUTH_TOKEN or both "
                "SERVICENOW_USERNAME and SERVICENOW_PASSWORD must be provided"
            )

        return cls(
            instance_url=instance_url,
            username=username,
            password=password,
            oauth_token=oauth_token,
            api_version=os.getenv("SERVICENOW_API_VERSION", "v2"),
            timeout=int(os.getenv("SERVICENOW_TIMEOUT", "30")),
            verify_ssl=os.getenv("SERVICENOW_VERIFY_SSL", "true").lower() == "true"
        )

    def get_table_api_url(self, table_name: str) -> str:
        """
        Get the full API URL for a ServiceNow table.

        Args:
            table_name: Name of the table (e.g., 'incident', 'sys_user')

        Returns:
            str: Full API URL
        """
        return f"{self.instance_url}/api/now/{self.api_version}/table/{table_name}"

    def get_record_url(self, table_name: str, sys_id: str) -> str:
        """
        Get the full API URL for a specific record.

        Args:
            table_name: Name of the table
            sys_id: System ID of the record

        Returns:
            str: Full API URL for the record
        """
        return f"{self.get_table_api_url(table_name)}/{sys_id}"


# Global config instance (initialized on first use)
_config: Optional[ServiceNowConfig] = None


def get_config() -> ServiceNowConfig:
    """
    Get the global ServiceNow configuration.

    The configuration is loaded from environment variables on first access
    and cached for subsequent calls.

    Returns:
        ServiceNowConfig: Configuration object

    Raises:
        ValueError: If required configuration is missing
    """
    global _config
    if _config is None:
        _config = ServiceNowConfig.from_environment()
    return _config


def set_config(config: ServiceNowConfig) -> None:
    """
    Set the global ServiceNow configuration.

    Useful for testing or when configuration needs to be set programmatically.

    Args:
        config: ServiceNowConfig object to use
    """
    global _config
    _config = config
