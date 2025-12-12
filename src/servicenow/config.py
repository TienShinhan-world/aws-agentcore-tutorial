"""
ServiceNow configuration management.

Loads ServiceNow credentials from AWS Secrets Manager and provides
helper methods for building API URLs and authentication.

Environment Variables:
    SERVICENOW_SECRET_NAME: Name of the Secrets Manager secret (default: servicenow/credentials)
    AWS_REGION: AWS region for Secrets Manager (default: eu-central-1)

Secret Schema (JSON in Secrets Manager):
    {
        "instance_url": "https://YOUR_INSTANCE.service-now.com",
        "username": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD"
    }
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class ServiceNowConfig:
    """ServiceNow configuration with credentials and instance URL."""

    instance_url: str
    username: str
    password: str

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Remove trailing slash from instance URL
        self.instance_url = self.instance_url.rstrip("/")

        # Ensure username and password are provided
        if not self.username or not self.password:
            raise ValueError(
                "ServiceNow configuration requires username and password"
            )

    @classmethod
    def from_secrets_manager(
        cls,
        secret_name: Optional[str] = None,
        region: Optional[str] = None,
    ) -> "ServiceNowConfig":
        """
        Load configuration from AWS Secrets Manager.

        Args:
            secret_name: Name of the secret in Secrets Manager.
                        Defaults to SERVICENOW_SECRET_NAME env var or 'servicenow/credentials'.
            region: AWS region. Defaults to AWS_REGION env var or 'eu-central-1'.

        Returns:
            ServiceNowConfig instance with loaded credentials.

        Raises:
            ClientError: If secret cannot be retrieved from Secrets Manager.
            ValueError: If secret is missing required fields.
        """
        secret_name = secret_name or os.environ.get(
            "SERVICENOW_SECRET_NAME", "servicenow/credentials"
        )
        region = region or os.environ.get("AWS_REGION", "eu-central-1")

        logger.info(f"Loading ServiceNow config from secret: {secret_name}")

        client = boto3.client("secretsmanager", region_name=region)

        try:
            response = client.get_secret_value(SecretId=secret_name)
            secret_string = response["SecretString"]
            secret_data = json.loads(secret_string)
        except ClientError as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise

        # Validate required fields
        required_fields = ["instance_url", "username", "password"]
        for field in required_fields:
            if field not in secret_data:
                raise ValueError(f"Secret {secret_name} missing required field: {field}")

        return cls(
            instance_url=secret_data["instance_url"],
            username=secret_data["username"],
            password=secret_data["password"],
        )

    @classmethod
    def from_environment(cls) -> "ServiceNowConfig":
        """
        Load configuration from environment variables.

        Environment Variables:
            SERVICENOW_INSTANCE_URL: ServiceNow instance URL (required)
            SERVICENOW_USERNAME: Username for basic auth (required)
            SERVICENOW_PASSWORD: Password for basic auth (required)

        Returns:
            ServiceNowConfig instance.

        Raises:
            ValueError: If required environment variables are missing.
        """
        instance_url = os.environ.get("SERVICENOW_INSTANCE_URL")
        username = os.environ.get("SERVICENOW_USERNAME")
        password = os.environ.get("SERVICENOW_PASSWORD")

        missing = []
        if not instance_url:
            missing.append("SERVICENOW_INSTANCE_URL")
        if not username:
            missing.append("SERVICENOW_USERNAME")
        if not password:
            missing.append("SERVICENOW_PASSWORD")

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            instance_url=instance_url,
            username=username,
            password=password,
        )

    def get_basic_auth(self) -> Tuple[str, str]:
        """
        Get basic auth credentials tuple for requests library.

        Returns:
            Tuple of (username, password).
        """
        return (self.username, self.password)

    def build_table_api_url(self, table: str, sys_id: Optional[str] = None) -> str:
        """
        Build ServiceNow Table API URL.

        Args:
            table: Table name (e.g., 'incident', 'sys_user').
            sys_id: Optional sys_id for specific record operations.

        Returns:
            Full API URL for the table endpoint.
        """
        base_url = f"{self.instance_url}/api/now/table/{table}"
        if sys_id:
            return f"{base_url}/{sys_id}"
        return base_url

    def build_api_url(self, endpoint: str) -> str:
        """
        Build arbitrary ServiceNow API URL.

        Args:
            endpoint: API endpoint path (e.g., '/api/now/table/incident').

        Returns:
            Full API URL.
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{self.instance_url}{endpoint}"
