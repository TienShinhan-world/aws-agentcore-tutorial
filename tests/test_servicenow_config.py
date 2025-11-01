"""
Tests for ServiceNow configuration module
"""
import pytest
from servicenow.config import ServiceNowConfig, get_config, set_config


@pytest.mark.unit
@pytest.mark.servicenow
class TestServiceNowConfig:
    """Tests for ServiceNowConfig class"""

    def test_config_initialization_with_basic_auth(self):
        """Test configuration initialization with username/password"""
        config = ServiceNowConfig(
            instance_url="https://test.service-now.com",
            username="test_user",
            password="test_password"
        )

        assert config.instance_url == "https://test.service-now.com"
        assert config.username == "test_user"
        assert config.password == "test_password"
        assert config.oauth_token is None
        assert config.api_version == "v2"
        assert config.timeout == 30
        assert config.verify_ssl is True

    def test_config_initialization_with_oauth(self):
        """Test configuration initialization with OAuth token"""
        config = ServiceNowConfig(
            instance_url="https://test.service-now.com",
            oauth_token="test_oauth_token"
        )

        assert config.instance_url == "https://test.service-now.com"
        assert config.oauth_token == "test_oauth_token"
        assert config.username is None
        assert config.password is None

    def test_config_strips_trailing_slash(self):
        """Test that trailing slash is removed from instance URL"""
        config = ServiceNowConfig(
            instance_url="https://test.service-now.com/",
            username="test",
            password="test"
        )

        # Note: The current implementation doesn't strip trailing slash in __init__
        # but does in from_environment. This test documents current behavior.
        assert config.instance_url == "https://test.service-now.com/"

    def test_config_from_environment_basic_auth(self, mock_env_vars):
        """Test loading configuration from environment with basic auth"""
        config = ServiceNowConfig.from_environment()

        assert config.instance_url == "https://test-instance.service-now.com"
        assert config.username == "test_user"
        assert config.password == "test_password"
        assert config.oauth_token is None
        assert config.api_version == "v2"
        assert config.timeout == 30
        assert config.verify_ssl is True

    def test_config_from_environment_oauth(self, mock_env_vars_oauth):
        """Test loading configuration from environment with OAuth"""
        config = ServiceNowConfig.from_environment()

        assert config.instance_url == "https://test-instance.service-now.com"
        assert config.oauth_token == "test_oauth_token_12345"
        assert config.username is None
        assert config.password is None

    def test_config_from_environment_missing_url(self, clear_env_vars):
        """Test that missing instance URL raises ValueError"""
        with pytest.raises(ValueError, match="SERVICENOW_INSTANCE_URL"):
            ServiceNowConfig.from_environment()

    def test_config_from_environment_missing_auth(self, monkeypatch, clear_env_vars):
        """Test that missing authentication raises ValueError"""
        monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://test.service-now.com")

        with pytest.raises(ValueError, match="Either SERVICENOW_OAUTH_TOKEN"):
            ServiceNowConfig.from_environment()

    def test_config_from_environment_incomplete_basic_auth(self, monkeypatch, clear_env_vars):
        """Test that incomplete basic auth raises ValueError"""
        monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://test.service-now.com")
        monkeypatch.setenv("SERVICENOW_USERNAME", "test_user")
        # Missing password

        with pytest.raises(ValueError, match="Either SERVICENOW_OAUTH_TOKEN"):
            ServiceNowConfig.from_environment()

    def test_config_from_environment_custom_values(self, monkeypatch, clear_env_vars):
        """Test custom configuration values from environment"""
        monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://custom.service-now.com")
        monkeypatch.setenv("SERVICENOW_USERNAME", "custom_user")
        monkeypatch.setenv("SERVICENOW_PASSWORD", "custom_pass")
        monkeypatch.setenv("SERVICENOW_API_VERSION", "v3")
        monkeypatch.setenv("SERVICENOW_TIMEOUT", "60")
        monkeypatch.setenv("SERVICENOW_VERIFY_SSL", "false")

        config = ServiceNowConfig.from_environment()

        assert config.instance_url == "https://custom.service-now.com"
        assert config.api_version == "v3"
        assert config.timeout == 60
        assert config.verify_ssl is False

    def test_get_table_api_url(self):
        """Test table API URL generation"""
        config = ServiceNowConfig(
            instance_url="https://test.service-now.com",
            username="test",
            password="test"
        )

        url = config.get_table_api_url("incident")
        assert url == "https://test.service-now.com/api/now/v2/table/incident"

    def test_get_table_api_url_custom_version(self):
        """Test table API URL with custom version"""
        config = ServiceNowConfig(
            instance_url="https://test.service-now.com",
            username="test",
            password="test",
            api_version="v3"
        )

        url = config.get_table_api_url("incident")
        assert url == "https://test.service-now.com/api/now/v3/table/incident"

    def test_get_record_url(self):
        """Test record URL generation"""
        config = ServiceNowConfig(
            instance_url="https://test.service-now.com",
            username="test",
            password="test"
        )

        url = config.get_record_url("incident", "abc123")
        assert url == "https://test.service-now.com/api/now/v2/table/incident/abc123"

    def test_global_config_singleton(self, mock_env_vars):
        """Test that get_config returns singleton instance"""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2
        assert config1.instance_url == "https://test-instance.service-now.com"

    def test_set_config(self):
        """Test manual configuration setting"""
        custom_config = ServiceNowConfig(
            instance_url="https://custom.service-now.com",
            username="custom",
            password="custom"
        )

        set_config(custom_config)
        retrieved_config = get_config()

        assert retrieved_config is custom_config
        assert retrieved_config.instance_url == "https://custom.service-now.com"

    def test_config_immutability_via_dataclass(self):
        """Test that config behaves like a dataclass"""
        config = ServiceNowConfig(
            instance_url="https://test.service-now.com",
            username="test",
            password="test"
        )

        # Config is a dataclass, so fields can be modified (not frozen)
        # This tests current behavior
        config.timeout = 60
        assert config.timeout == 60
